# WebRTC is used only by the omitted desktop camera UI.
if (NOT TARGET LibDataChannel::LibDataChannel)
    add_library(LibDataChannel::LibDataChannel INTERFACE IMPORTED GLOBAL)
endif ()
