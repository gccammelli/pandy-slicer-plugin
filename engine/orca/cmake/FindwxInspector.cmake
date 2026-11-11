# The desktop widget inspector is not compiled into the headless CLI.
set(wxInspector_DIR "${CMAKE_SOURCE_DIR}/../../build/orca/headers/lib/cmake/wxInspector")
file(MAKE_DIRECTORY "${CMAKE_SOURCE_DIR}/../../build/orca/headers/include")
if (NOT TARGET wxInspector::wxInspector)
    add_library(wxInspector::wxInspector INTERFACE IMPORTED GLOBAL)
endif ()
set(wxInspector_FOUND TRUE)
