//! The XML-plist subset usbmuxd actually needs.
//!
//! usbmuxd speaks XML plists. Rather than take a dependency, the subset the
//! protocol uses is implemented here — dictionaries of strings, integers and
//! booleans, plus one array of dictionaries in a `ListDevices` reply.
//!
//! The reader is **strict**: an unsupported element is an error rather than
//! being skipped, so a reply shaped differently from the decoded protocol
//! fails visibly instead of silently yielding a half-parsed value. That
//! strictness is the reason this is worth keeping even though `libplist` is
//! now installed.
//!
//! Keys are held in a `BTreeMap`, so serialisation is deterministic. The
//! body's exact text is nonetheless **not** part of conformance: usbmuxd
//! parses XML, so two writers may legitimately differ in whitespace and key
//! order. The protocol pins the 16-byte header, and that is what is compared.

use std::collections::BTreeMap;

use crate::{protocol_error, Result};

pub type Dict = BTreeMap<String, Value>;

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    Integer(i64),
    String(String),
    Dict(Dict),
    Array(Vec<Value>),
    Data(Vec<u8>),
}

impl Value {
    pub fn as_bool(&self) -> Result<bool> {
        match self {
            Value::Bool(v) => Ok(*v),
            _ => Err(protocol_error!("plist value is not a boolean")),
        }
    }

    pub fn as_integer(&self) -> Result<i64> {
        match self {
            Value::Integer(v) => Ok(*v),
            _ => Err(protocol_error!("plist value is not an integer")),
        }
    }

    pub fn as_string(&self) -> Result<&str> {
        match self {
            Value::String(v) => Ok(v),
            _ => Err(protocol_error!("plist value is not a string")),
        }
    }

    pub fn as_dict(&self) -> Result<&Dict> {
        match self {
            Value::Dict(v) => Ok(v),
            _ => Err(protocol_error!("plist value is not a dict")),
        }
    }

    pub fn as_array(&self) -> Result<&Vec<Value>> {
        match self {
            Value::Array(v) => Ok(v),
            _ => Err(protocol_error!("plist value is not an array")),
        }
    }

    /// A dictionary member, or `Null` when absent — which keeps the common
    /// "is this key present and right" check to one call.
    pub fn get(&self, key: &str) -> &Value {
        match self {
            Value::Dict(dict) => dict.get(key).unwrap_or(&Value::Null),
            _ => &Value::Null,
        }
    }

    pub fn is_null(&self) -> bool {
        matches!(self, Value::Null)
    }
}

fn escape(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            _ => out.push(c),
        }
    }
    out
}

const BASE64: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

fn base64(data: &[u8]) -> String {
    let mut out = String::new();
    for chunk in data.chunks(3) {
        let b = [
            chunk[0],
            *chunk.get(1).unwrap_or(&0),
            *chunk.get(2).unwrap_or(&0),
        ];
        let n = ((b[0] as u32) << 16) | ((b[1] as u32) << 8) | b[2] as u32;
        out.push(BASE64[(n >> 18) as usize & 63] as char);
        out.push(BASE64[(n >> 12) as usize & 63] as char);
        out.push(if chunk.len() > 1 {
            BASE64[(n >> 6) as usize & 63] as char
        } else {
            '='
        });
        out.push(if chunk.len() > 2 {
            BASE64[n as usize & 63] as char
        } else {
            '='
        });
    }
    out
}

fn indent(out: &mut String, depth: usize) {
    for _ in 0..depth {
        out.push('\t');
    }
}

fn write(out: &mut String, value: &Value, depth: usize) {
    match value {
        Value::Null => {}
        Value::Bool(v) => {
            indent(out, depth);
            out.push_str(if *v { "<true/>\n" } else { "<false/>\n" });
        }
        Value::Integer(v) => {
            indent(out, depth);
            out.push_str(&format!("<integer>{v}</integer>\n"));
        }
        Value::String(v) => {
            indent(out, depth);
            out.push_str(&format!("<string>{}</string>\n", escape(v)));
        }
        Value::Data(v) => {
            indent(out, depth);
            out.push_str(&format!("<data>{}</data>\n", base64(v)));
        }
        Value::Dict(dict) => {
            if dict.is_empty() {
                indent(out, depth);
                out.push_str("<dict/>\n");
                return;
            }
            indent(out, depth);
            out.push_str("<dict>\n");
            for (key, item) in dict {
                indent(out, depth + 1);
                out.push_str(&format!("<key>{}</key>\n", escape(key)));
                write(out, item, depth + 1);
            }
            indent(out, depth);
            out.push_str("</dict>\n");
        }
        Value::Array(items) => {
            if items.is_empty() {
                indent(out, depth);
                out.push_str("<array/>\n");
                return;
            }
            indent(out, depth);
            out.push_str("<array>\n");
            for item in items {
                write(out, item, depth + 1);
            }
            indent(out, depth);
            out.push_str("</array>\n");
        }
    }
}

pub fn dumps(value: &Value) -> String {
    let mut out = String::from(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n\
         <!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \
         \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n\
         <plist version=\"1.0\">\n",
    );
    write(&mut out, value, 0);
    out.push_str("</plist>\n");
    out
}

// --- Reading ---------------------------------------------------------------

struct Parser<'a> {
    text: &'a str,
    pos: usize,
}

impl<'a> Parser<'a> {
    fn skip_space(&mut self) {
        while self.pos < self.text.len() && self.text.as_bytes()[self.pos].is_ascii_whitespace() {
            self.pos += 1;
        }
    }

    /// Skips XML declarations, DOCTYPEs and comments, which carry nothing this
    /// protocol needs.
    fn skip_prologue(&mut self) -> Result<()> {
        loop {
            self.skip_space();
            let rest = &self.text[self.pos..];
            if rest.starts_with("<?") {
                let end = rest
                    .find("?>")
                    .ok_or_else(|| protocol_error!("unterminated XML declaration"))?;
                self.pos += end + 2;
            } else if rest.starts_with("<!DOCTYPE") {
                let end = rest
                    .find('>')
                    .ok_or_else(|| protocol_error!("unterminated DOCTYPE"))?;
                self.pos += end + 1;
            } else if rest.starts_with("<!--") {
                let end = rest
                    .find("-->")
                    .ok_or_else(|| protocol_error!("unterminated comment"))?;
                self.pos += end + 3;
            } else {
                return Ok(());
            }
        }
    }

    fn read_tag(&mut self) -> Result<String> {
        self.skip_space();
        if self.pos >= self.text.len() || self.text.as_bytes()[self.pos] != b'<' {
            return Err(protocol_error!("expected a tag at offset {}", self.pos));
        }
        let rest = &self.text[self.pos..];
        let end = rest
            .find('>')
            .ok_or_else(|| protocol_error!("unterminated tag"))?;
        let tag = rest[1..end].to_string();
        self.pos += end + 1;
        Ok(tag)
    }

    fn read_text_until_close(&mut self, name: &str) -> Result<String> {
        let close = format!("</{name}>");
        let rest = &self.text[self.pos..];
        let end = rest
            .find(&close)
            .ok_or_else(|| protocol_error!("unterminated <{name}>"))?;
        let body = rest[..end].to_string();
        self.pos += end + close.len();
        Ok(unescape(&body))
    }

    fn parse_value(&mut self) -> Result<Value> {
        let tag = self.read_tag()?;
        self.parse_value_with_tag(&tag)
    }

    fn parse_value_with_tag(&mut self, tag: &str) -> Result<Value> {
        match tag {
            "true/" => Ok(Value::Bool(true)),
            "false/" => Ok(Value::Bool(false)),
            "dict/" => Ok(Value::Dict(Dict::new())),
            "array/" => Ok(Value::Array(Vec::new())),
            "integer" => {
                let body = self.read_text_until_close("integer")?;
                body.trim()
                    .parse::<i64>()
                    .map(Value::Integer)
                    .map_err(|_| protocol_error!("bad integer: {body}"))
            }
            "string" => Ok(Value::String(self.read_text_until_close("string")?)),
            "data" => Ok(Value::Data(
                self.read_text_until_close("data")?.into_bytes(),
            )),
            "dict" => {
                let mut dict = Dict::new();
                loop {
                    let inner = self.read_tag()?;
                    if inner == "/dict" {
                        return Ok(Value::Dict(dict));
                    }
                    if inner != "key" {
                        return Err(protocol_error!("expected <key> in a dict, got <{inner}>"));
                    }
                    let key = self.read_text_until_close("key")?;
                    let value = self.parse_value()?;
                    dict.insert(key, value);
                }
            }
            "array" => {
                let mut items = Vec::new();
                loop {
                    self.skip_space();
                    let save = self.pos;
                    let inner = self.read_tag()?;
                    if inner == "/array" {
                        return Ok(Value::Array(items));
                    }
                    self.pos = save;
                    items.push(self.parse_value()?);
                }
            }
            other => Err(protocol_error!("unsupported plist element <{other}>")),
        }
    }
}

fn unescape(text: &str) -> String {
    text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
}

pub fn loads(xml: &str) -> Result<Value> {
    let mut parser = Parser { text: xml, pos: 0 };
    parser.skip_prologue()?;
    let tag = parser.read_tag()?;
    if !tag.starts_with("plist") {
        return Err(protocol_error!("document is not a <plist>, got <{tag}>"));
    }
    parser.parse_value()
}
