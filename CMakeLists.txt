cmake_minimum_required(VERSION 3.16)
project(sixeyes_host VERSION 0.0.1 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(SIXEYES_BUILD_TESTS "Build the C++ tests" ON)

add_library(sixeyes_core STATIC core/src/codec.cpp core/src/serial.cpp core/src/c_api.cpp)
target_include_directories(sixeyes_core PUBLIC core/include protocol/generated)
if(MSVC)
  target_compile_options(sixeyes_core PRIVATE /W4)
else()
  target_compile_options(sixeyes_core PRIVATE -Wall -Wextra)
endif()

if(SIXEYES_BUILD_TESTS)
  enable_testing()
  add_executable(test_codec core/tests/test_codec.cpp)
  target_link_libraries(test_codec PRIVATE sixeyes_core)
  target_include_directories(test_codec PRIVATE core/tests)
  add_test(NAME codec COMMAND test_codec)
endif()
