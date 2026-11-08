// A deliberately tiny test harness.
//
// The project's Python suite uses unittest; pulling in GoogleTest for the C++
// core would add a dependency to a layer whose whole point is to need almost
// nothing. This is enough: named cases, assertions that report file and line,
// and a non-zero exit on failure.
#pragma once

#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <functional>
#include <iomanip>
#include <sstream>
#include <type_traits>
#include <string>
#include <vector>

namespace testing {

struct Case {
  std::string name;
  std::function<void()> fn;
};

inline std::vector<Case>& registry() {
  static std::vector<Case> cases;
  return cases;
}

struct Registrar {
  Registrar(const std::string& name, std::function<void()> fn) {
    registry().push_back({name, std::move(fn)});
  }
};

class Failure : public std::runtime_error {
 public:
  explicit Failure(const std::string& what) : std::runtime_error(what) {}
};

// One template with `if constexpr` rather than an overload pair: a separate
// non-template overload for Bytes loses to the template here, which then
// fails to compile because std::vector has no operator<<.
template <typename T>
std::string show(const T& value) {
  std::ostringstream out;
  if constexpr (std::is_same_v<T, std::vector<std::uint8_t>>) {
    out << value.size() << " bytes:";
    for (std::size_t i = 0; i < value.size() && i < 48; ++i) {
      out << ' ' << std::hex << std::setw(2) << std::setfill('0')
          << static_cast<int>(value[i]);
    }
    if (value.size() > 48) out << " ...";
  } else if constexpr (std::is_same_v<T, std::uint8_t>) {
    out << static_cast<int>(value);
  } else {
    out << value;
  }
  return out.str();
}

inline int run_all() {
  int failures = 0;
  for (const Case& c : registry()) {
    try {
      c.fn();
      std::printf(".");
    } catch (const std::exception& e) {
      ++failures;
      std::printf("\nFAIL %s\n     %s\n", c.name.c_str(), e.what());
    }
  }
  std::printf("\n%zu tests, %d failures\n", registry().size(), failures);
  return failures == 0 ? 0 : 1;
}

}  // namespace testing

#define HASHI_CONCAT_(a, b) a##b
#define HASHI_CONCAT(a, b) HASHI_CONCAT_(a, b)

#define TEST(name)                                                      \
  static void HASHI_CONCAT(test_fn_, __LINE__)();                       \
  static ::testing::Registrar HASHI_CONCAT(test_reg_, __LINE__)(        \
      name, HASHI_CONCAT(test_fn_, __LINE__));                          \
  static void HASHI_CONCAT(test_fn_, __LINE__)()

#define CHECK(cond)                                                     \
  do {                                                                  \
    if (!(cond)) {                                                      \
      throw ::testing::Failure(std::string(__FILE__) + ":" +            \
                               std::to_string(__LINE__) +               \
                               " CHECK failed: " #cond);                \
    }                                                                   \
  } while (0)

#define CHECK_EQ(a, b)                                                  \
  do {                                                                  \
    auto va_ = (a);  /* by value: a reference would dangle when the   */ \
    auto vb_ = (b);  /* argument is a temporary, e.g. *optional       */ \
    if (!(va_ == vb_)) {                                                \
      throw ::testing::Failure(                                         \
          std::string(__FILE__) + ":" + std::to_string(__LINE__) +      \
          " CHECK_EQ failed: " #a " != " #b "\n       left:  " +        \
          ::testing::show(va_) + "\n       right: " + ::testing::show(vb_)); \
    }                                                                   \
  } while (0)

#define CHECK_THROWS(expr)                                              \
  do {                                                                  \
    bool threw_ = false;                                                \
    try { (void)(expr); } catch (const std::exception&) { threw_ = true; } \
    if (!threw_) {                                                      \
      throw ::testing::Failure(std::string(__FILE__) + ":" +            \
                               std::to_string(__LINE__) +               \
                               " expected a throw from: " #expr);       \
    }                                                                   \
  } while (0)
