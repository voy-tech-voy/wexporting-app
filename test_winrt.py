import winrt.windows.services.store as store
import asyncio

async def test_store():
    ctx = store.StoreContext.get_default()
    print("StoreContext:", ctx)
    
    # Try different interop imports
    try:
        from winrt.windows.ui.core.interop import WindowInteropWrapper
        print("Found WindowInteropWrapper")
    except Exception as e:
        print("No WindowInteropWrapper:", e)
        
    try:
        import winrt.system
        print("winrt.system attributes:", [x for x in dir(winrt.system) if not x.startswith('_')])
        if hasattr(winrt.system, 'Object'):
            print("winrt.system.Object attributes:", [x for x in dir(winrt.system.Object) if not x.startswith('_')])
    except Exception as e:
        print("Error with winrt.system:", e)
        
    # Try the new interop module for initialize_with_window
    try:
        import winrt.windows.ui.core as core
        print("core attributes:", [x for x in dir(core) if not x.startswith('_')])
    except Exception as e:
        print("Error with core:", e)
    
    # Check if pywinrt exposes initialize_with_window directly on StoreContext in newer versions
    if hasattr(ctx, 'initialize_with_window'):
        print("ctx HAS initialize_with_window!")
        
    print("\n--- Testing get_store_products_async ---")
    try:
        res = await ctx.get_store_products_async(["Consumable", "Durable"], ["9PFHR7GMBT0T", "9NNK6Q3WZN2M"])
        print("Products lookup mapping:", res.products)
        if res.products:
            for k, v in res.products.items():
                print("Found Product:", k, v.title)
        else:
            print("No products found in mapping")
            
        print("\n--- Testing get_store_products_async with ['Product'] ---")
        res2 = await ctx.get_store_products_async(["Product"], ["9PFHR7GMBT0T", "9NNK6Q3WZN2M"])
        print("Products lookup mapping with 'Product':", res2.products)
        if res2.products:
            for k, v in res2.products.items():
                print("Found Product:", k, v.title)
        else:
            print("No products found in mapping with 'Product'")
            
    except Exception as e:
        print("Error getting products:", e)

asyncio.run(test_store())
