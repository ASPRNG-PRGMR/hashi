// A minimal XML property-list reader and writer, scoped to usbmux.
//
// usbmuxd speaks XML plists. The full format is large; the subset this
// protocol uses is not — dictionaries of strings, integers and booleans, plus
// one array of dictionaries in a ListDevices reply. Rather than take a
// dependency on libplist (whose development package is not installed here),
// this implements exactly that subset and tests it against the real replies.
//
// The reader is deliberately strict: unknown element types raise rather than
// being skipped, so a reply shaped differently from the decoded protocol is a
// visible failure instead of silently missing data.
#pragma once

#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include "hashi/bytes.hpp"

namespace hashi::plist {

class Value;
using Dict = std::map<std::string, Value>;
using Array = std::vector<Value>;

// The two container enumerators are spelled Dictionary and List rather than
// Dict and Array so that they do not reuse the names of the aliases above.
// Reusing them is legal -- a scoped enumerator is only reachable as
// Type::Dict, so it cannot actually hide the alias -- but GCC's -Wshadow
// reports it anyway, and a C++20 `using enum Type` would make the clash
// real. Distinct names cost nothing and keep the warning honest.
enum class Type { Null, Bool, Integer, String, Dictionary, List, Data };

/// One plist node. Copyable; nesting is held by value through shared storage
/// so that a Dict can contain Values without an incomplete-type problem.
class Value {
 public:
  Value();
  Value(bool v);                 // NOLINT(google-explicit-constructor)
  Value(std::int64_t v);         // NOLINT(google-explicit-constructor)
  Value(int v);                  // NOLINT(google-explicit-constructor)
  Value(const char* v);          // NOLINT(google-explicit-constructor)
  Value(std::string v);          // NOLINT(google-explicit-constructor)
  Value(Dict v);                 // NOLINT(google-explicit-constructor)
  Value(Array v);                // NOLINT(google-explicit-constructor)
  static Value data(Bytes v);

  Type type() const { return type_; }
  bool is_null() const { return type_ == Type::Null; }

  bool as_bool() const;
  std::int64_t as_integer() const;
  const std::string& as_string() const;
  const Dict& as_dict() const;
  const Array& as_array() const;
  const Bytes& as_data() const;

  /// Dictionary lookup that returns a Null Value when the key is absent,
  /// so callers can probe optional keys without exceptions.
  const Value& get(const std::string& key) const;

 private:
  Type type_ = Type::Null;
  bool bool_ = false;
  std::int64_t integer_ = 0;
  std::string string_;
  Bytes data_;
  std::shared_ptr<Dict> dict_;
  std::shared_ptr<Array> array_;
};

/// Serialise a value as an XML plist document, including the XML declaration
/// and DOCTYPE that usbmuxd's parser expects to see.
std::string dumps(const Value& value);

/// Parse an XML plist document. Throws ProtocolError on anything outside the
/// supported subset.
Value loads(const std::string& xml);

}  // namespace hashi::plist
