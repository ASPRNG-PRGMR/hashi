#include "hashi/plist.hpp"

#include <cctype>
#include <sstream>

namespace hashi::plist {
namespace {

const Value kNull{};

void indent(std::ostringstream& out, int depth) {
  for (int i = 0; i < depth; ++i) out << '\t';
}

std::string escape(const std::string& text) {
  std::string out;
  out.reserve(text.size());
  for (char c : text) {
    switch (c) {
      case '&': out += "&amp;"; break;
      case '<': out += "&lt;"; break;
      case '>': out += "&gt;"; break;
      default: out += c;
    }
  }
  return out;
}

const char kBase64[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

std::string base64(const Bytes& data) {
  std::string out;
  std::size_t i = 0;
  while (i + 2 < data.size()) {
    std::uint32_t n = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2];
    out += kBase64[(n >> 18) & 63];
    out += kBase64[(n >> 12) & 63];
    out += kBase64[(n >> 6) & 63];
    out += kBase64[n & 63];
    i += 3;
  }
  if (i + 1 == data.size()) {
    std::uint32_t n = data[i] << 16;
    out += kBase64[(n >> 18) & 63];
    out += kBase64[(n >> 12) & 63];
    out += "==";
  } else if (i + 2 == data.size()) {
    std::uint32_t n = (data[i] << 16) | (data[i + 1] << 8);
    out += kBase64[(n >> 18) & 63];
    out += kBase64[(n >> 12) & 63];
    out += kBase64[(n >> 6) & 63];
    out += '=';
  }
  return out;
}

void write(std::ostringstream& out, const Value& value, int depth);

void write_dict(std::ostringstream& out, const Dict& dict, int depth) {
  if (dict.empty()) {
    indent(out, depth);
    out << "<dict/>\n";
    return;
  }
  indent(out, depth);
  out << "<dict>\n";
  for (const auto& [key, item] : dict) {
    indent(out, depth + 1);
    out << "<key>" << escape(key) << "</key>\n";
    write(out, item, depth + 1);
  }
  indent(out, depth);
  out << "</dict>\n";
}

void write(std::ostringstream& out, const Value& value, int depth) {
  switch (value.type()) {
    case Type::Bool:
      indent(out, depth);
      out << (value.as_bool() ? "<true/>\n" : "<false/>\n");
      break;
    case Type::Integer:
      indent(out, depth);
      out << "<integer>" << value.as_integer() << "</integer>\n";
      break;
    case Type::String:
      indent(out, depth);
      out << "<string>" << escape(value.as_string()) << "</string>\n";
      break;
    case Type::Data:
      indent(out, depth);
      out << "<data>" << base64(value.as_data()) << "</data>\n";
      break;
    case Type::Dictionary:
      write_dict(out, value.as_dict(), depth);
      break;
    case Type::List: {
      const Array& items = value.as_array();
      if (items.empty()) {
        indent(out, depth);
        out << "<array/>\n";
        break;
      }
      indent(out, depth);
      out << "<array>\n";
      for (const auto& item : items) write(out, item, depth + 1);
      indent(out, depth);
      out << "</array>\n";
      break;
    }
    case Type::Null:
      throw ProtocolError("cannot serialise a null plist value");
  }
}

// ---------------------------------------------------------------------------
// Reader
// ---------------------------------------------------------------------------

struct Parser {
  const std::string& text;
  std::size_t pos = 0;

  void skip_space() {
    while (pos < text.size() &&
           std::isspace(static_cast<unsigned char>(text[pos]))) {
      ++pos;
    }
  }

  // Skips XML declarations, DOCTYPEs and comments, which carry nothing we need.
  void skip_prologue() {
    for (;;) {
      skip_space();
      if (text.compare(pos, 4, "<?xm") == 0 ||
          text.compare(pos, 2, "<?") == 0) {
        std::size_t end = text.find("?>", pos);
        if (end == std::string::npos) throw ProtocolError("unterminated <?...?>");
        pos = end + 2;
      } else if (text.compare(pos, 4, "<!--") == 0) {
        std::size_t end = text.find("-->", pos);
        if (end == std::string::npos) throw ProtocolError("unterminated comment");
        pos = end + 3;
      } else if (text.compare(pos, 9, "<!DOCTYPE") == 0) {
        std::size_t end = text.find('>', pos);
        if (end == std::string::npos) throw ProtocolError("unterminated DOCTYPE");
        pos = end + 1;
      } else {
        return;
      }
    }
  }

  std::string read_tag() {
    skip_prologue();
    if (pos >= text.size() || text[pos] != '<') {
      throw ProtocolError("expected an element at offset " +
                          std::to_string(pos));
    }
    std::size_t end = text.find('>', pos);
    if (end == std::string::npos) throw ProtocolError("unterminated tag");
    std::string tag = text.substr(pos + 1, end - pos - 1);
    pos = end + 1;
    return tag;
  }

  std::string read_text_until_close(const std::string& name) {
    std::string close = "</" + name + ">";
    std::size_t end = text.find(close, pos);
    if (end == std::string::npos) {
      throw ProtocolError("unterminated <" + name + ">");
    }
    std::string body = text.substr(pos, end - pos);
    pos = end + close.size();
    // Unescape the entities the writer produces.
    std::string out;
    for (std::size_t i = 0; i < body.size();) {
      if (body.compare(i, 5, "&amp;") == 0) { out += '&'; i += 5; }
      else if (body.compare(i, 4, "&lt;") == 0) { out += '<'; i += 4; }
      else if (body.compare(i, 4, "&gt;") == 0) { out += '>'; i += 4; }
      else if (body.compare(i, 6, "&quot;") == 0) { out += '"'; i += 6; }
      else if (body.compare(i, 6, "&apos;") == 0) { out += '\''; i += 6; }
      else { out += body[i]; ++i; }
    }
    return out;
  }

  Value parse_value() {
    std::string tag = read_tag();
    if (!tag.empty() && tag.back() == '/') {
      std::string name = tag.substr(0, tag.size() - 1);
      if (name == "true") return Value(true);
      if (name == "false") return Value(false);
      if (name == "dict") return Value(Dict{});
      if (name == "array") return Value(Array{});
      if (name == "string") return Value(std::string{});
      throw ProtocolError("unsupported empty element <" + name + "/>");
    }
    if (tag == "true") { read_text_until_close("true"); return Value(true); }
    if (tag == "false") { read_text_until_close("false"); return Value(false); }
    if (tag == "integer") {
      std::string body = read_text_until_close("integer");
      try {
        return Value(static_cast<std::int64_t>(std::stoll(body)));
      } catch (const std::exception&) {
        throw ProtocolError("bad <integer> value: " + body);
      }
    }
    if (tag == "string") return Value(read_text_until_close("string"));
    if (tag == "data") {
      // Not produced by usbmux replies we handle; kept as a string so the
      // document still parses rather than failing on an unused field.
      return Value(read_text_until_close("data"));
    }
    if (tag == "dict") {
      Dict dict;
      for (;;) {
        skip_space();
        if (text.compare(pos, 7, "</dict>") == 0) { pos += 7; break; }
        std::string key_tag = read_tag();
        if (key_tag != "key") {
          throw ProtocolError("expected <key> in <dict>, got <" + key_tag + ">");
        }
        std::string key = read_text_until_close("key");
        dict.emplace(std::move(key), parse_value());
      }
      return Value(std::move(dict));
    }
    if (tag == "array") {
      Array items;
      for (;;) {
        skip_space();
        if (text.compare(pos, 8, "</array>") == 0) { pos += 8; break; }
        items.push_back(parse_value());
      }
      return Value(std::move(items));
    }
    throw ProtocolError("unsupported plist element <" + tag + ">");
  }
};

}  // namespace

Value::Value() = default;
Value::Value(bool v) : type_(Type::Bool), bool_(v) {}
Value::Value(std::int64_t v) : type_(Type::Integer), integer_(v) {}
Value::Value(int v) : type_(Type::Integer), integer_(v) {}
Value::Value(const char* v) : type_(Type::String), string_(v) {}
Value::Value(std::string v) : type_(Type::String), string_(std::move(v)) {}
Value::Value(Dict v)
    : type_(Type::Dictionary), dict_(std::make_shared<Dict>(std::move(v))) {}
Value::Value(Array v)
    : type_(Type::List), array_(std::make_shared<Array>(std::move(v))) {}

Value Value::data(Bytes v) {
  Value out;
  out.type_ = Type::Data;
  out.data_ = std::move(v);
  return out;
}

bool Value::as_bool() const {
  if (type_ != Type::Bool) throw ProtocolError("plist value is not a boolean");
  return bool_;
}

std::int64_t Value::as_integer() const {
  if (type_ != Type::Integer) throw ProtocolError("plist value is not an integer");
  return integer_;
}

const std::string& Value::as_string() const {
  if (type_ != Type::String) throw ProtocolError("plist value is not a string");
  return string_;
}

const Dict& Value::as_dict() const {
  if (type_ != Type::Dictionary) throw ProtocolError("plist value is not a dict");
  return *dict_;
}

const Array& Value::as_array() const {
  if (type_ != Type::List) throw ProtocolError("plist value is not an array");
  return *array_;
}

const Bytes& Value::as_data() const {
  if (type_ != Type::Data) throw ProtocolError("plist value is not data");
  return data_;
}

const Value& Value::get(const std::string& key) const {
  if (type_ != Type::Dictionary) return kNull;
  auto it = dict_->find(key);
  return it == dict_->end() ? kNull : it->second;
}

std::string dumps(const Value& value) {
  std::ostringstream out;
  out << "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
         "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
         "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
         "<plist version=\"1.0\">\n";
  write(out, value, 0);
  out << "</plist>\n";
  return out.str();
}

Value loads(const std::string& xml) {
  Parser parser{xml};
  parser.skip_prologue();
  std::string tag = parser.read_tag();
  if (tag.rfind("plist", 0) != 0) {
    throw ProtocolError("document is not a <plist>, got <" + tag + ">");
  }
  Value value = parser.parse_value();
  return value;
}

}  // namespace hashi::plist
