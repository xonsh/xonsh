#include <Python.h>
#include <stdlib.h>
#include <string.h>
#include <utmpx.h>
#ifdef __APPLE__
#include <sys/sysctl.h>
#endif
#include <sys/time.h>


/*
The reason this exists as a full-blown C extension instead of as a pure-Python
function using ctypes is that while POSIX specifies utmpx, it does not specify
the values of its various constants or the order or size of struct utmpx's
members. In practice, all of these things vary, and there's no way for us to
find any of them at runtime from Python.
*/

double _calc_uptime(struct timeval bt) {
    struct timeval tv;
    /* Get current time. */
    if (gettimeofday(&tv, NULL) != 0) {
        return -1;
    }

    /* Subtract boot time from current time. */
    if (tv.tv_usec < bt.tv_usec) {
        tv.tv_sec--;
        tv.tv_usec = 1000000 - bt.tv_usec + tv.tv_usec;
    } else {
        tv.tv_usec -= bt.tv_usec;
    }
    tv.tv_sec -= bt.tv_sec;

    return (unsigned)tv.tv_sec + (unsigned)tv.tv_usec / 1000000.0;
}

#ifdef __APPLE__
static PyObject*
_uptime_osx(PyObject *self, PyObject *args)
{
    struct timeval bt;
    size_t len = sizeof(bt);

    /* Unused arguments. */
    (void)self;
    (void)args;

    /* Get boot time if it's there. */
    if (sysctlbyname("kern.boottime", &bt, &len, NULL, 0) != 0) {
        Py_RETURN_NONE;
    }

    return Py_BuildValue("d", _calc_uptime(bt));
}
#else
// Other systems might not use sysctl
static PyObject*
_uptime_osx(PyObject *self, PyObject *args) {
    Py_RETURN_NONE
}
#endif


static PyObject*
_uptime_posix(PyObject *self, PyObject *args)
{
    struct utmpx id = {.ut_type = BOOT_TIME}, *res;
    struct timeval bt;

    /* Unused arguments. */
    (void)self;
    (void)args;

    /* Get boot time if it's there. */
    if ((res = getutxid(&id)) == NULL) {
        endutxent();
        Py_RETURN_NONE;
    }
    memcpy(&bt, &(res->ut_tv), sizeof(struct timeval));
    endutxent();

    return Py_BuildValue("d", _calc_uptime(bt));
}

static PyMethodDef _uptime_methods[] = {
    {"_uptime_posix", _uptime_posix, METH_NOARGS,
     "Fallback uptime for POSIX."},
    {"_uptime_osx", _uptime_osx, METH_NOARGS,
        "Uptime for OS X"},
    {NULL, NULL, 0, NULL}
};

#if PY_MAJOR_VERSION >= 3

static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "uptime._posix",
    "Fallback uptime for POSIX.",
    -1,
    _uptime_methods,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC
PyInit__posix(void)
{
    return PyModule_Create(&moduledef);
}

#else

PyMODINIT_FUNC
init_posix(void)
{
    Py_InitModule("_posix", _uptime_methods);
}

#endif