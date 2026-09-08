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

Then, to start the test controller:

1. Add the root of the repository to your PYTHONPATH.

2. From the root directory of the repository, enter the pixi environment:

    ``$ pixi shell -e bacnet-test-controller``

3. From the same directory as when running ``g36conftest``, start the controller device with:

    ``$ python <path_to_run_device>/run_device.py -ai 1 -s 1 --ini <path_to_.ini file>``

    Use arguments ``-ai`` to set the refresh interval and ``-s`` to set the controller
    advance time step for each refresh.  The script defaults for those arguments 
    are equal to 5, which would advance the controller 5 seconds every 5 seconds of real time.
    However, we suggest using 1 for each argument as above, advancing the controller 1 second
    every 1 second of real time.

    Use argument ``--ini`` to set the full path to the bacpypes configuration file, which is located
    at ``tests/bacnet/BACpypes.ini``.

Then, to start the conformance test, use the typical steps associated with running 
``g36conftest`` in a separate process, except specify a ``bacnet`` configuration instead of ``simulation``.



