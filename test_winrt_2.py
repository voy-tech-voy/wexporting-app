import winrt.windows.services.store as store
ctx = store.StoreContext.get_default()

import ctypes

try:
    print("ctx id:", id(ctx))
    # Python 3 pywinrt stores the IUnknown pointer in a PyCapsule or native extension.
    # What attributes are on ctx?
    print("dir(ctx):", [x for x in dir(ctx) if not x.startswith('__')])
    
    # Is there a winrt._winrt?
    import winrt
    print("dir(winrt):", [x for x in dir(winrt) if not x.startswith('__')])
    
    # Try testing get_store_products_async with ["Consumable", "Durable", "UnmanagedConsumable"]
    import asyncio
    async def test():
        res = await ctx.get_store_products_async(["Consumable", "Durable", "UnmanagedConsumable"], ["9PFHR7GMBT0T", "9NNK6Q3WZN2M"])
        for k, v in res.products.items():
            print("Found:", k, v.title)
    asyncio.run(test())
except Exception as e:
    print("Error:", e)
