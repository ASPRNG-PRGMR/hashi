cmake_minimum_required(VERSION 3.20)
project(hashi_native CXX)

# C++17 as chosen for the port: RAII matters here because the live layers
# juggle a D-Bus connection, two sessions, a GStreamer pipeline and a socket,
# and the faults the first live run produced were teardown-ordering ones.
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_library(hashi_protocol STATIC
  src/plist.cpp
  src/usbmux.cpp
  src/startup.cpp
  src/stream.cpp
)
target_include_directories(hashi_protocol PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(hashi_protocol PRIVATE
  -Wall -Wextra -Wpedantic -Wconversion -Wshadow)

# The protocol core deliberately has no dependencies beyond the standard
# library. usbmuxd speaks XML plists and libplist's development package is not
# installed here, so the small subset this needs is implemented and tested
# rather than pulled in. The later milestones (GIO for Mutter's D-Bus,
# GStreamer for capture, libjpeg-turbo for encoding) link their own.

enable_testing()
add_executable(test_protocol tests/test_protocol.cpp)
target_link_libraries(test_protocol PRIVATE hashi_protocol)
target_include_directories(test_protocol PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/tests)
target_compile_options(test_protocol PRIVATE -Wall -Wextra)
add_test(NAME protocol COMMAND test_protocol)

# Emits the core's wire bytes for native/tools/conformance.py to diff against
# the Python reference implementation.
add_executable(dump_vectors tools/dump_vectors.cpp)
target_link_libraries(dump_vectors PRIVATE hashi_protocol)
