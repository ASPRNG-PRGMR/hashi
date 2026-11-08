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
  src/jpeg.cpp
  src/gnome.cpp
)
target_include_directories(hashi_protocol PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(hashi_protocol PRIVATE
  -Wall -Wextra -Wpedantic -Wconversion -Wshadow)

# The protocol core deliberately has no dependencies beyond the standard
# library -- src/jpeg.cpp belongs to it because the frame prelude is marker
# bytes built from published Annex K tables, not an encoder. usbmuxd speaks XML
# plists and libplist's development package was missing when this was written,
# so the small subset this needs is implemented and tested rather than pulled
# in. Layers that genuinely need a library link it in their own target below.

find_package(PkgConfig REQUIRED)

# --- Live Mutter session ----------------------------------------------------
# GIO for the D-Bus calls. Separate from the contract layer in hashi_protocol,
# which builds the same arguments without linking anything -- that is what lets
# conformance check them with no compositor running.
pkg_check_modules(GIO REQUIRED IMPORTED_TARGET gio-2.0)

add_library(hashi_session STATIC src/session.cpp)
target_link_libraries(hashi_session PUBLIC hashi_protocol PkgConfig::GIO)
target_compile_options(hashi_session PRIVATE
  -Wall -Wextra -Wpedantic -Wconversion -Wshadow)

# --- Frame encoding ---------------------------------------------------------
# libjpeg-turbo through its own TurboJPEG API. The Python reference reaches the
# same library through Pillow, and the conformance harness checks that the two
# agree on bytes rather than assuming that "both use libjpeg" is enough.
pkg_check_modules(TURBOJPEG REQUIRED IMPORTED_TARGET libturbojpeg)

add_library(hashi_encode STATIC src/encoder.cpp)
target_link_libraries(hashi_encode PUBLIC hashi_protocol
                                   PRIVATE PkgConfig::TURBOJPEG)
target_compile_options(hashi_encode PRIVATE
  -Wall -Wextra -Wpedantic -Wconversion -Wshadow)

enable_testing()
add_executable(test_protocol tests/test_protocol.cpp)
target_link_libraries(test_protocol PRIVATE hashi_protocol)
target_include_directories(test_protocol PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/tests)
target_compile_options(test_protocol PRIVATE -Wall -Wextra)
add_test(NAME protocol COMMAND test_protocol)

# The encoder's tests link libjpeg-turbo, so they are a separate binary from
# the dependency-free core's.
add_executable(test_encode tests/test_encode.cpp)
target_link_libraries(test_encode PRIVATE hashi_encode)
target_include_directories(test_encode PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/tests)
target_compile_options(test_encode PRIVATE -Wall -Wextra)
add_test(NAME encode COMMAND test_encode)

# Emits the core's wire bytes for native/tools/conformance.py to diff against
# the Python reference implementation.
add_executable(dump_vectors tools/dump_vectors.cpp)
target_link_libraries(dump_vectors PRIVATE hashi_protocol)

# The session layer's bus-free tests: variant shapes and refusals.
add_executable(test_session tests/test_session.cpp)
target_link_libraries(test_session PRIVATE hashi_session)
target_include_directories(test_session PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/tests)
target_compile_options(test_session PRIVATE -Wall -Wextra)
add_test(NAME session COMMAND test_session)

# Emits the real GVariant payloads as GLib's own text form, so the harness can
# check that PropValue -> GVariant lands what PyGObject builds. Creates no
# session and makes no D-Bus call.
add_executable(dump_variants tools/dump_variants.cpp)
target_link_libraries(dump_variants PRIVATE hashi_session)
target_compile_options(dump_variants PRIVATE -Wall -Wextra)

# Encodes one raw-RGB fixture so the harness can diff a whole frame, scan data
# included, against what Pillow produces from the same pixels.
add_executable(dump_frame tools/dump_frame.cpp)
target_link_libraries(dump_frame PRIVATE hashi_encode)
target_compile_options(dump_frame PRIVATE -Wall -Wextra)
