# Injected into Bambu Studio's own top-level CMakeLists.txt with -DCMAKE_PROJECT_INCLUDE=<this file>, so upstream's
# build (options, flags, definitions, dependency lookup) runs unmodified. Once upstream has defined all its targets,
# engine.cmake adds the Pandy Studio engine target next to upstream's BambuStudio target. CMake runs this file after
# every project() call, including those of bundled subprojects: only the top-level one schedules the engine.
get_property(_pandy_scheduled GLOBAL PROPERTY PANDY_ENGINE_SCHEDULED)
if (NOT _pandy_scheduled AND CMAKE_CURRENT_SOURCE_DIR STREQUAL CMAKE_SOURCE_DIR)
    set_property(GLOBAL PROPERTY PANDY_ENGINE_SCHEDULED TRUE)
    cmake_language(EVAL CODE "cmake_language(DEFER DIRECTORY [[${CMAKE_SOURCE_DIR}]] CALL include [[${CMAKE_CURRENT_LIST_DIR}/engine.cmake]])")
endif ()
