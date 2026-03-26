import sys
import trace

# Create a trace object
tracer = trace.Trace(
    ignoredirs=[sys.prefix, sys.exec_prefix],
    trace=1,
    count=0
)

# Run the import under tracer
tracer.run('import client.plugins.presets.ui')
