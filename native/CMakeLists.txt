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

# --- PipeWire capture -------------------------------------------------------
# GStreamer, with the app plugin for appsink's pull API.
pkg_check_modules(GST REQUIRED IMPORTED_TARGET gstreamer-1.0 gstreamer-app-1.0)

add_library(hashi_capture STATIC src/capture.cpp)
target_link_libraries(hashi_capture PUBLIC hashi_encode PkgConfig::GST)
target_compile_options(hashi_capture PRIVATE
  -Wall -Wextra -Wpedantic -Wconversion -Wshadow)

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

# libjpeg-turbo 3.0 replaced the whole TurboJPEG entry-point family -- tj3Init
# and tj3Compress8 for tjInitCompress and tjCompress2 -- with no compatibility
# shim, so which one src/encoder.cpp may call is decided here rather than left
# to a header probe. 3.x is preferred because it is the only one that can set
# the JFIF density through the API; the 2.x path reaches the same bytes but has
# to write the density into APP0 itself. See the note at the top of that file.
if(TURBOJPEG_VERSION VERSION_GREATER_EQUAL 3.0)
  set(hashi_tj3_default ON)
else()
  set(hashi_tj3_default OFF)
endif()
option(HASHI_USE_TURBOJPEG3
  "Use the libjpeg-turbo 3.x tj3* API. Off builds the 2.x fallback, which is \
byte-identical and can be selected deliberately to test it."
  ${hashi_tj3_default})

if(HASHI_USE_TURBOJPEG3)
  message(STATUS
    "libjpeg-turbo ${TURBOJPEG_VERSION}: encoding through the tj3* API")
else()
  message(STATUS
    "libjpeg-turbo ${TURBOJPEG_VERSION}: encoding through the legacy tj* API")
  if(TURBOJPEG_VERSION VERSION_GREATER_EQUAL 3.0)
    message(STATUS
      "  (3.x is installed; the fallback was selected explicitly)")
  endif()
endif()

add_library(hashi_encode STATIC src/encoder.cpp)
target_link_libraries(hashi_encode PUBLIC hashi_protocol
                                   PRIVATE PkgConfig::TURBOJPEG)
target_compile_definitions(hashi_encode PRIVATE
  HASHI_HAVE_TURBOJPEG3=$<BOOL:${HASHI_USE_TURBOJPEG3}>)
target_compile_options(hashi_encode PRIVATE
  -Wall -Wextra -Wpedantic -Wconversion -Wshadow)

# --- The composed host ------------------------------------------------------
# Transport, pacing and the loop. The only socket I/O in the native tree.
add_library(hashi_host STATIC src/host.cpp)
target_link_libraries(hashi_host PUBLIC hashi_capture hashi_session)
target_compile_options(hashi_host PRIVATE
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
# Links hashi_host for the pipeline description and the pacer, which are a
# plain string and plain arithmetic. That is a tool linking a library, not a
# dependency of the core: hashi_protocol itself still links nothing but the
# standard library.
add_executable(dump_vectors tools/dump_vectors.cpp)
target_link_libraries(dump_vectors PRIVATE hashi_protocol hashi_host)

# The host binary. `plan` and `devices` are inert; `run` needs --allow-session.
add_executable(hashi tools/hashi.cpp)
target_link_libraries(hashi PRIVATE hashi_host)
target_compile_options(hashi PRIVATE -Wall -Wextra)

# The host layer's tests: pacing, the frame gate, and the socket over a
# socketpair. No device and no compositor.
add_executable(test_host tests/test_host.cpp)
target_link_libraries(test_host PRIVATE hashi_host)
target_include_directories(test_host PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/tests)
target_compile_options(test_host PRIVATE -Wall -Wextra)
add_test(NAME host COMMAND test_host)

# The capture layer's compositor-free tests.
add_executable(test_capture tests/test_capture.cpp)
target_link_libraries(test_capture PRIVATE hashi_capture)
target_include_directories(test_capture PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/tests)
target_compile_options(test_capture PRIVATE -Wall -Wextra)
add_test(NAME capture COMMAND test_capture)

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
