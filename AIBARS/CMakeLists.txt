cmake_minimum_required(VERSION 3.16)
project(AIBARS VERSION 2.3.2 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(AIBARS_ENABLE_WARNINGS "Enable strict compiler warnings" ON)

add_library(aibars_core
    src/types.cpp
    src/simulator.cpp
    src/detector.cpp
    src/diagnostics.cpp
    src/black_box.cpp
    src/recovery.cpp
)
target_include_directories(aibars_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)

function(aibars_enable_warnings target)
  if(AIBARS_ENABLE_WARNINGS)
    if(MSVC)
      target_compile_options(${target} PRIVATE /W4 /permissive-)
    else()
      target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
    endif()
  endif()
endfunction()

add_executable(aibars_sim src/main.cpp)
target_link_libraries(aibars_sim PRIVATE aibars_core)

add_executable(aibars_tests tests/test_core.cpp)
target_link_libraries(aibars_tests PRIVATE aibars_core)

aibars_enable_warnings(aibars_core)
aibars_enable_warnings(aibars_sim)
aibars_enable_warnings(aibars_tests)

enable_testing()
add_test(NAME aibars_core_tests COMMAND aibars_tests)
