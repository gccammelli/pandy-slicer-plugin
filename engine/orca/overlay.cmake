# Injected into OrcaSlicer's own top-level CMakeLists.txt with -DCMAKE_PROJECT_INCLUDE=<this file>, so upstream's
# build (options, flags, definitions, dependency lookup) runs unmodified. Once upstream has defined all its targets,
# engine.cmake adds the Pandy Studio engine target next to upstream's OrcaSlicer target. CMake runs this file after
# every project() call, including those of bundled subprojects: only the top-level one schedules the engine.
get_property(_pandy_scheduled GLOBAL PROPERTY PANDY_ENGINE_SCHEDULED)
if (NOT _pandy_scheduled AND CMAKE_CURRENT_SOURCE_DIR STREQUAL CMAKE_SOURCE_DIR)
    # FFmpeg is required at configure time by the unused desktop video target.
    # No FFmpeg headers or libraries are exposed to pandy-engine.
    file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/pandy-gui-pkgconfig")
    foreach (_av libavformat libavcodec libswscale libavutil)
        file(WRITE "${CMAKE_BINARY_DIR}/pandy-gui-pkgconfig/${_av}.pc"
            "Name: ${_av}\nDescription: omitted desktop video dependency\nVersion: 61.0.0\nLibs:\nCflags:\n")
    endforeach ()
    set(ENV{PKG_CONFIG_PATH} "${CMAKE_BINARY_DIR}/pandy-gui-pkgconfig:$ENV{PKG_CONFIG_PATH}")
    list(PREPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/cmake")
    set(LibDataChannel_DIR "${CMAKE_CURRENT_LIST_DIR}/cmake" CACHE PATH "Headless GUI-only dependency")
    set_property(GLOBAL PROPERTY PANDY_ENGINE_SCHEDULED TRUE)
    cmake_language(EVAL CODE "cmake_language(DEFER DIRECTORY [[${CMAKE_SOURCE_DIR}]] CALL include [[${CMAKE_CURRENT_LIST_DIR}/engine.cmake]])")
endif ()
