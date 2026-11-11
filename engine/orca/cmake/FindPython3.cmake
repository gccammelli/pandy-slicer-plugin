# Orca embeds Python only in its desktop plugin UI, which pandy-engine does not
# compile. Keep the declared GUI target configurable without linking a Python
# runtime into the slicing engine. Any reached GUI function must still trap.
if (NOT TARGET Python3::Python)
    add_library(Python3::Python INTERFACE IMPORTED GLOBAL)
endif ()
set(Python3_FOUND TRUE)
