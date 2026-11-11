# wx-config validates the full desktop GTK dependency list even for our headless
# target. Resolve those configure-only libraries on the host; engine.cmake only
# links target wx archives and drops GTK/WebView/media from the static engine.
set(_pandy_wx_root_mode "${CMAKE_FIND_ROOT_PATH_MODE_LIBRARY}")
set(_pandy_wx_library_path "${CMAKE_LIBRARY_PATH}")
if(CMAKE_CROSSCOMPILING)
    set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY BOTH)
    list(PREPEND CMAKE_LIBRARY_PATH /usr/lib/x86_64-linux-gnu)
endif()
include("${CMAKE_ROOT}/Modules/FindwxWidgets.cmake")
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY "${_pandy_wx_root_mode}")
set(CMAKE_LIBRARY_PATH "${_pandy_wx_library_path}")
unset(_pandy_wx_library_path)
unset(_pandy_wx_root_mode)
