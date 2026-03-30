import ctypes
import winrt.windows.services.store as store

ctx = store.StoreContext.get_default()

class PyWinRTObject(ctypes.Structure):
    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type", ctypes.c_void_p),
        ("com_ptr", ctypes.c_void_p)
    ]

# IInitializeWithWindow: 3E68D4BD-7135-4D10-8018-9FB6D9F33FA1
class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8)
    ]
    def __init__(self, data1, data2, data3, data4):
        super().__init__()
        self.Data1 = data1
        self.Data2 = data2
        self.Data3 = data3
        for i in range(8):
            self.Data4[i] = data4[i]

IID_IInitializeWithWindow = GUID(
    0x3E68D4BD, 0x7135, 0x4D10, 
    (0x80, 0x18, 0x9F, 0xB6, 0xD9, 0xF3, 0x3F, 0xA1)
)

try:
    obj = PyWinRTObject.from_address(id(ctx))
    print(f"com_ptr: {hex(obj.com_ptr)}")
    
    if obj.com_ptr:
        vtable_p = ctypes.cast(obj.com_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
        vtable = vtable_p[0]
        
        QueryInterface = ctypes.WINFUNCTYPE(
            ctypes.c_uint,          # HRESULT
            ctypes.c_void_p,        # this
            ctypes.POINTER(GUID),   # IID
            ctypes.POINTER(ctypes.c_void_p) # ppvObject
        )(vtable[0])
        
        Release = ctypes.WINFUNCTYPE(ctypes.c_uint, ctypes.c_void_p)(vtable[2])
        
        init_with_window_ptr = ctypes.c_void_p()
        hr = QueryInterface(obj.com_ptr, ctypes.byref(IID_IInitializeWithWindow), ctypes.byref(init_with_window_ptr))
        
        print(f"QueryInterface HRESULT: {hex(hr)}")
        if hr == 0:
            print(f"IInitializeWithWindow com_ptr: {hex(init_with_window_ptr.value)}")
            Release(init_with_window_ptr)
            
except Exception as e:
    print("Error:", e)
