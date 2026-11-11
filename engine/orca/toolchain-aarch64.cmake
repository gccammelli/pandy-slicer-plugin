# Reuse Android's GUI-header lookups and floating-point settings, but match the
# Orca release's Clang 18 / libstdc++ 14 toolchain. Wrappers also serve autotools.
include("${CMAKE_CURRENT_LIST_DIR}/../toolchains/aarch64-linux-gnu.cmake")
set(CMAKE_C_COMPILER "${CMAKE_CURRENT_LIST_DIR}/cc-aarch64")
set(CMAKE_CXX_COMPILER "${CMAKE_CURRENT_LIST_DIR}/cxx-aarch64")
set(CMAKE_EXE_LINKER_FLAGS_INIT "-fuse-ld=/usr/bin/ld.lld-18")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "-fuse-ld=/usr/bin/ld.lld-18")
# Unlike GCC's header, Clang's NEON declarations cannot be parsed with FMA
# undefined. Hide it only after including arm_neon.h (see no-fma.h).
foreach (_lang C CXX)
    string(REPLACE "-U__ARM_FEATURE_FMA" "-include ${CMAKE_CURRENT_LIST_DIR}/no-fma.h"
        CMAKE_${_lang}_FLAGS_INIT "${CMAKE_${_lang}_FLAGS_INIT}")
    if (CMAKE_${_lang}_FLAGS MATCHES "-U__ARM_FEATURE_FMA")
        string(REPLACE "-U__ARM_FEATURE_FMA" "-include ${CMAKE_CURRENT_LIST_DIR}/no-fma.h"
            _flags "${CMAKE_${_lang}_FLAGS}")
        set(CMAKE_${_lang}_FLAGS "${_flags}" CACHE STRING "Compiler flags" FORCE)
    endif ()
endforeach ()

# The pinned source encoding check is a build-host executable; x86 validates the same source.
set(SLIC3R_ENC_CHECK OFF CACHE BOOL "" FORCE)
