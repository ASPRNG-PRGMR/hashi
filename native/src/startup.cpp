#include "hashi/startup.hpp"

#include <cctype>
#include <string>

namespace hashi::startup {
namespace {

// A JSON scanner just large enough for the capability gate.
//
// The gate needs three things: that the block is a valid JSON document, that
// it holds a `diff_jpeg` member, and that the member is boolean true. A full
// parser is more than that needs, but string-matching would be less faithful:
// the agent genuinely parses, and a malformed document must fail the gate
// rather than appear to contain a key. So this validates structure while
// recording only the one member that matters.
struct JsonScanner {
  const std::string& text;
  std::size_t pos = 0;
  bool found_diff_jpeg = false;
  bool diff_jpeg_is_bool = false;
  bool diff_jpeg_value = false;
  int depth = 0;

  void skip_space() {
    while (pos < text.size() &&
           std::isspace(static_cast<unsigned char>(text[pos]))) {
      ++pos;
    }
  }

  bool literal(const char* word) {
    const std::size_t n = std::char_traits<char>::length(word);
    if (text.compare(pos, n, word) != 0) return false;
    pos += n;
    return true;
  }

  // Returns the string's contents; throws on a malformed string.
  std::string parse_string() {
    if (pos >= text.size() || text[pos] != '"') throw ProtocolError("expected a string");
    ++pos;
    std::string out;
    while (pos < text.size()) {
      char c = text[pos++];
      if (c == '"') return out;
      if (c == '\\') {
        if (pos >= text.size()) break;
        char esc = text[pos++];
        switch (esc) {
          case 'n': out += '\n'; break;
          case 't': out += '\t'; break;
          case 'r': out += '\r'; break;
          case 'b': out += '\b'; break;
          case 'f': out += '\f'; break;
          case '/': out += '/'; break;
          case '"': out += '"'; break;
          case '\\': out += '\\'; break;
          case 'u': {
            if (pos + 4 > text.size()) throw ProtocolError("bad \\u escape");
            pos += 4;             // not decoded; no key we care about uses it
            out += '?';
            break;
          }
          default: throw ProtocolError("bad escape in string");
        }
      } else {
        out += c;
      }
    }
    throw ProtocolError("unterminated string");
  }

  void parse_number() {
    const std::size_t start = pos;
    if (pos < text.size() && (text[pos] == '-' || text[pos] == '+')) ++pos;
    bool digits = false;
    while (pos < text.size() && std::isdigit(static_cast<unsigned char>(text[pos]))) {
      ++pos;
      digits = true;
    }
    if (pos < text.size() && text[pos] == '.') {
      ++pos;
      while (pos < text.size() && std::isdigit(static_cast<unsigned char>(text[pos]))) {
        ++pos;
        digits = true;
      }
    }
    if (pos < text.size() && (text[pos] == 'e' || text[pos] == 'E')) {
      ++pos;
      if (pos < text.size() && (text[pos] == '-' || text[pos] == '+')) ++pos;
      while (pos < text.size() && std::isdigit(static_cast<unsigned char>(text[pos]))) ++pos;
    }
    if (!digits) throw ProtocolError("bad number at offset " + std::to_string(start));
  }

  void parse_value() {
    skip_space();
    if (pos >= text.size()) throw ProtocolError("unexpected end of document");
    const char c = text[pos];
    if (c == '{') { parse_object(); return; }
    if (c == '[') { parse_array(); return; }
    if (c == '"') { parse_string(); return; }
    if (literal("true") || literal("false") || literal("null")) return;
    parse_number();
  }

  void parse_object() {
    ++pos;  // '{'
    ++depth;
    skip_space();
    if (pos < text.size() && text[pos] == '}') { ++pos; --depth; return; }
    for (;;) {
      skip_space();
      const std::string key = parse_string();
      skip_space();
      if (pos >= text.size() || text[pos] != ':') throw ProtocolError("expected ':'");
      ++pos;
      skip_space();

      // Only a top-level member counts: the agent reads the key off the root
      // document, not out of a nested object.
      const bool top_level = depth == 1;
      if (top_level && key == kCapabilityDiffJpeg) {
        found_diff_jpeg = true;
        const std::size_t before = pos;
        if (literal("true")) {
          diff_jpeg_is_bool = true;
          diff_jpeg_value = true;
        } else if (literal("false")) {
          diff_jpeg_is_bool = true;
          diff_jpeg_value = false;
        } else {
          pos = before;
          diff_jpeg_is_bool = false;
          parse_value();
        }
      } else {
        parse_value();
      }

      skip_space();
      if (pos < text.size() && text[pos] == ',') { ++pos; continue; }
      if (pos < text.size() && text[pos] == '}') { ++pos; --depth; return; }
      throw ProtocolError("expected ',' or '}' in object");
    }
  }

  void parse_array() {
    ++pos;  // '['
    ++depth;
    skip_space();
    if (pos < text.size() && text[pos] == ']') { ++pos; --depth; return; }
    for (;;) {
      parse_value();
      skip_space();
      if (pos < text.size() && text[pos] == ',') { ++pos; continue; }
      if (pos < text.size() && text[pos] == ']') { ++pos; --depth; return; }
      throw ProtocolError("expected ',' or ']' in array");
    }
  }
};

}  // namespace

Bytes encode_header(std::uint8_t record_type, std::uint32_t payload_len) {
  if (payload_len > 0xFFFFFF) {
    throw ProtocolError("payload length " + std::to_string(payload_len) +
                        " does not fit in 24 bits");
  }
  Bytes out;
  out.reserve(4);
  out.push_back(record_type);
  put_be24(out, payload_len);
  return out;
}

HeaderFields decode_header(const std::uint8_t* header, std::size_t len) {
  if (len != 4) {
    throw ProtocolError("header must be exactly 4 bytes, got " +
                        std::to_string(len));
  }
  return HeaderFields{header[0], get_be24(header + 1)};
}

Bytes encode_control(std::uint32_t field0, std::uint32_t field1,
                     std::uint32_t field2, bool network_order,
                     bool raw_field1) {
  const std::uint8_t record_type = network_order ? kTypeControl : kTypeControlLegacy;
  Bytes out = encode_header(record_type, kControlPayloadLen);
  if (network_order) put_be32(out, field0); else put_le32(out, field0);
  // The 0xfc record's field 1 is stored with no htonl — the agent's own
  // inconsistency, confirmed by the captured little-endian 5.
  if (network_order && !raw_field1) put_be32(out, field1); else put_le32(out, field1);
  if (network_order) put_be32(out, field2); else put_le32(out, field2);
  return out;
}

ControlRecord decode_control(const Bytes& record, bool network_order) {
  if (record.size() != 4 + kControlPayloadLen) {
    throw ProtocolError("control record must be 16 bytes, got " +
                        std::to_string(record.size()));
  }
  const HeaderFields header = decode_header(record.data(), 4);
  if (header.payload_len != kControlPayloadLen) {
    throw ProtocolError("control record announces " +
                        std::to_string(header.payload_len) +
                        " payload bytes, expected 12");
  }
  const std::uint8_t* p = record.data() + 4;
  ControlRecord out{header.record_type, 0, 0, 0};
  if (network_order) {
    out.field0 = get_be32(p);
    out.field1 = get_be32(p + 4);
    out.field2 = get_be32(p + 8);
  } else {
    out.field0 = get_le32(p);
    out.field1 = get_le32(p + 4);
    out.field2 = get_le32(p + 8);
  }
  return out;
}

Bytes encode_byte_order_probe() {
  Bytes out;
  put_le32(out, 4);
  return out;
}

bool probe_reply_accepted(const Bytes& reply) {
  return !reply.empty() && reply[0] == 4;
}

std::vector<Bytes> host_startup_sequence(bool network_order) {
  return {
      encode_byte_order_probe(),
      encode_control(kMsgHello, 0, 0, network_order),
      encode_control(kMsgReady, 0, 0, network_order),
      encode_control(kMsgExtraRequest, 5, 0, network_order, /*raw_field1=*/true),
  };
}

std::uint32_t align_client_dimension(std::uint32_t value) {
  if (value == 0) return 0;
  return ((value - 1) & ~3u) + 4u;
}

Dimensions parse_hello_ack(const Bytes& record, bool network_order) {
  const ControlRecord control = decode_control(record, network_order);
  if (control.field0 != kMsgHelloAck) {
    throw ProtocolError("hello ack unknown type: expected 2, got " +
                        std::to_string(control.field0));
  }
  return Dimensions{align_client_dimension(control.field1),
                    align_client_dimension(control.field2)};
}

void parse_ready_ack(const Bytes& record, bool network_order) {
  const ControlRecord control = decode_control(record, network_order);
  if (control.field0 != kMsgReadyAck) {
    throw ProtocolError("ready ack unknown type: expected 255, got " +
                        std::to_string(control.field0));
  }
}

std::uint32_t extra_data_length(const std::uint8_t* header, std::size_t len) {
  const HeaderFields fields = decode_header(header, len);
  if (fields.payload_len == 0) {
    throw ProtocolError("recv extra data length failed: announced length is zero");
  }
  return fields.payload_len;
}

bool diff_jpeg_enabled(const Bytes& body) {
  if (body.empty()) return false;
  const std::string text(body.begin(), body.end());
  JsonScanner scanner{text};
  try {
    scanner.skip_space();
    if (scanner.pos >= text.size()) return false;
    // "A valid JSON document must be either an array or an object value."
    const char first = text[scanner.pos];
    if (first != '{' && first != '[') return false;
    scanner.parse_value();
  } catch (const ProtocolError&) {
    return false;
  }
  return scanner.found_diff_jpeg && scanner.diff_jpeg_is_bool &&
         scanner.diff_jpeg_value;
}

}  // namespace hashi::startup
