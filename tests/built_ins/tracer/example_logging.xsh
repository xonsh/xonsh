# Regression script for xonsh/xonsh#4924.
# Creating a `logging.Handler` registers a `_removeHandlerRef` weakref callback
# that fires during interpreter shutdown. Combined with `trace on`, that callback
# re-enters `TracerType.trace` while `xonsh.tracer`'s globals are being cleared.
# Without default-arg bindings inside `trace()`, the imported names resolve to
# None and Python emits "Exception ignored in: <function _removeHandlerRef ...>"
# on stderr. The test runner asserts an empty stderr, so this script will fail
# the test if the regression returns.
import logging
logging.StreamHandler()
trace on
echo OK
