import winrt.windows.services.store as store
import ctypes

ctx = store.StoreContext.get_default()

class PyWinRTObject(ctypes.Structure):
    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type", ctypes.c_void_p),
        ("com_ptr", ctypes.c_void_p)
    ]

try:
    obj = PyWinRTObject.from_address(id(ctx))
    print(f"com_ptr: {hex(obj.com_ptr)}")
    
    if obj.com_ptr:
        vtable_p = ctypes.cast(obj.com_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
        vtable = vtable_p[0]
        AddRef = ctypes.WINFUNCTYPE(ctypes.c_uint, ctypes.c_void_p)(vtable[1])
        Release = ctypes.WINFUNCTYPE(ctypes.c_uint, ctypes.c_void_p)(vtable[2])
        print("AddRef:", AddRef(obj.com_ptr))
        print("Release:", Release(obj.com_ptr))
except Exception as e:
    print("Error:", e)
