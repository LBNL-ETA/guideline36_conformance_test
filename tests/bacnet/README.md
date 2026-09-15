Overview
--------

``run_device.py`` can be used to deploy an emulated BACnet device 
for testing the conformance test software using the bacnet device interface.
It compiles the Modelica model specified in the conformance test 
configuration for ``simulation`` into an FMU, 
using ``src/g36conftest/device/simulation_device.py`` and OpenModelica, 
and runs the FMU within a BACnet device harness set up by bacpypes.

Usage
-----
It requires the correct point mapping to be set in
``conformance_tests/{test_type}/config`` and the correct
.ttl file to be present as ``conformance_tests/{test_type}/config/{test_type}.ttl``,
which can be created using ``conformance_tests/{test_type}/config/create_ttl.py``
once the point mapping file is set up.

1. From the [tests directory](..), start the test controller:
    `$pixi run -e bacnet-test-controller python bacnet/run_device.py -ai 1 -s 1 --ini bacnet/BACpypes.ini`

    Use arguments ``-ai`` to set the refresh interval and ``-s`` to set the controller
    advance time step for each refresh.  The script defaults for those arguments 
    are equal to 5, which would advance the controller 5 seconds every 5 seconds of real time.
    However, we suggest using 1 for each argument as above, advancing the controller 1 second
    every 1 second of real time.

    Use argument ``--ini`` to set the full path to the bacpypes configuration file, which is located
    at ``bacnet/BACpypes.ini``.

2. Then, to start the conformance test, use the typical steps associated with running 
``g36conftest`` in a separate process, except specify a ``bacnet`` configuration instead of ``simulation``.
 Inline example: `$pixi run -e bacnet g36conftest <...>`.



