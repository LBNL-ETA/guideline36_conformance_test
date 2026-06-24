# -*- coding: utf-8 -*-

"""
This code is a modified version of bacnet/BopTestProxy.py from BOPTEST and is modified according to the license below,
and found at https://github.com/ibpsa/project1-boptest/blob/master/license.md.

----------------------------------------------------------------------------------------------
BOPTEST. Copyright (c) 2018-2025
International Building Performance Simulation Association (IBPSA) and
contributors.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice,a
  this list of conditions and the following disclaimer in the documentation and/or
  other materials provided with the distribution.
* Neither the name of the copyright holder nor the names of its contributors may be used
  to endorse or promote products derived from this software
  without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

You are under no obligation whatsoever to provide any bug fixes, patches,
or upgrades to the features, functionality or performance of the source code
("Enhancements") to anyone; however, if you choose to make your Enhancements
available either publicly, or directly to its copyright holders,
without imposing a separate written license agreement for such
Enhancements, then you hereby grant the following license: a non-exclusive,
royalty-free perpetual license to install, use, modify, prepare derivative
works, incorporate into other computer software, distribute, and sublicense
such enhancements or derivative works thereof, in binary and source code form.

Note: The license is a revised 3 clause BSD license with an ADDED paragraph
at the end that makes it easy to accept improvements.
----------------------------------------------------------------------------------------------

CoPPER Proxy Device

This code is based on a prototype written by Erik Paulson (https://github.com/epaulson/boptest-bacnet-proxy)
and is based on the BACpypes Python package distributed under an
MIT License.

"""

import os
import time
import json
import rdflib
from pathlib import Path
from ..utils.config_loader import load_config

from bacpypes.debugging import bacpypes_debugging, ModuleLogger
from bacpypes.consolelogging import ConfigArgumentParser

from bacpypes.core import run
from bacpypes.task import RecurringTask

from bacpypes.basetypes import DateTime
from bacpypes.primitivedata import Real
from bacpypes.object import AnalogValueObject, DateTimeValueObject

from bacpypes.app import BIPSimpleApplication
from bacpypes.service.device import DeviceCommunicationControlServices
from bacpypes.service.object import ReadWritePropertyMultipleServices
from bacpypes.local.device import LocalDeviceObject
from bacpypes.local.object import AnalogValueCmdObject, Commandable, AnalogOutputCmdObject
from bacpypes.object import register_object_type, AnalogInputObject

# some debugging
_debug = 0
_log = ModuleLogger(globals())

# dictionary of names to objects
objects = {}
inputs = {}
activation_signal = {}
nextState = None
g = None

boptest_measurements = None
boptest_inputs = None
advance_counter = 0

# TODO - what should some of the BOPTEST objects be - maybe
# AnalogInputs or BinaryInputs?
# Not currently using this class
# TODO - why does BACpyes have a builtin AnalogValueCmdObject but not a builtin AnalogInputCmdObject?
@bacpypes_debugging
@register_object_type(vendor_id=999)
class AnalogInputCmdObject(Commandable(Real), AnalogInputObject):
    def _set_value(self, value):
        if _debug:
            AnalogInputCmdObject._debug("_set_value %r", value)

        # numeric values are easy to set
        self.presentValue = value

# We are using this class
# TODO - why are we using this class instead of just AnalogValueCmdObject?
# This was how OpenWeatherServer.py did it - was it just so it could log the change?
@bacpypes_debugging
@register_object_type(vendor_id=999)
class LocalAnalogValueObject(AnalogValueCmdObject):
    def _set_value(self, value):
        if _debug:
            LocalAnalogValueObject._debug("_set_value %r", value)

        # numeric values are easy to set
        self.presentValue = value

klassMapping = {'analog-value': LocalAnalogValueObject, 'analog-input': AnalogInputObject, 'analog-output': AnalogOutputCmdObject}
unitMapping = {'K': "degreesKelvin", 'ppm': "partsPerMillion"}


@bacpypes_debugging
def create_objects(app, configfile, oncommand):
    """Create the objects that hold the result values.

    Parameters
    ----------
    configfile : str
        File path for .ttl BACnet objects configuration file.
    oncommand : bool
        Indicator of whether app refresh interval is =on-command by user.

    """

    if _debug:
        create_objects._debug("create_objects %r", app)
    global objects, inputs, g, nextState

    g= rdflib.Graph()
    g.parse(configfile)
    points = g.query("select ?point ?name ?bacnetRef ?statusFlags ?unit where {?point ref:hasExternalReference ?bo . ?bo bacnet:object-identifier ?bacnetRef . ?bo bacnet:object-name ?name . ?bo bacnet:status-flags ?statusFlags OPTIONAL {?point brick:hasUnit ?unit} }")
    for point in points:
        rdfBacnetName = point[1]
        rdfBacnetRef = point[2]
        rdfStatusFlags = point[3]
        rdfBacnetUnit = point[4]

        if _debug:
            create_objects._debug("    - name: %r", point[1])
        klassName, instanceNum = rdfBacnetRef.split(",", 2)
        klass = klassMapping[klassName]
        instanceNum = int(instanceNum)
        name = str(rdfBacnetName)
        units = None
        if rdfBacnetUnit:
            units = unitMapping[str(rdfBacnetUnit)]

        initialValue = None
        if nextState is not None:
            initialValue = nextState[name]
        else:
            initialValue = 0.0

        statusFlagsList=[int(str(rdfStatusFlags))]

        if klassName == 'analog-input' or klassName == 'analog-value':
            obj = klass(objectName = name, objectIdentifier=(klass.objectType, instanceNum), presentValue=initialValue,statusFlags=statusFlagsList)
        else:
            obj = klass(objectName = name, objectIdentifier=(klass.objectType, instanceNum), presentValue=initialValue, relinquishDefault = initialValue,statusFlags=statusFlagsList)
        if _debug:
            create_objects._debug("    - obj: %r", obj)

        if units is not None:
            obj.units = units

        # add it to the application
        app.add_object(obj)
        # keep track of the object by name
        objects[name] = obj
        if name in boptest_inputs:
            inputs[name] = obj
        elif name in 'advance':
            inputs[name] = obj

@bacpypes_debugging
class BOPTESTUpdater(RecurringTask):

    """
    An instance of this class pops up out of the ground every once in a
    while and write out the next value.
    """

    def __init__(self, interval, oncommand):

        self.oncommand = oncommand
        # if oncommand == True start counter at 0 and simulation advances
        # when advance input > self.advance_counter. If oncommand == false
        # self.advance_counter == -1 and simulation advances automatically
        if self.oncommand:
            self.advance_counter = 0
        else:
            self.advance_counter = -1

        if _debug:
            self._debug("__init__ %r", interval)
            self._debug("__init__ %r", oncommand)
            self._debug("__init__ Setting advance counter")
            self._debug("__init__ %r", self.advance_counter)
        RecurringTask.__init__(self, interval)

        # install it
        self.install_task()

    def process_task(self):
        """Read the current simulation data from the API and set the object values."""

        global objects, inputs, controller, advance_counter

        if _debug and (advance_counter > self.advance_counter):
            self._debug("update_boptest_data")
        # ask the web service
        # We get results direct from /advance now but you could ask the simulation for historic data
        # response = requests.put(
        #    "http://localhost:5000/results", json={'point_name':'TRooAir_y', 'start_time': timestep * 30, 'final_time': (timestep+1)*30}
        #)

        signals = {}

        # For "commandable" objects, BACnet maintains a priorityArray that can be written to from levels 1-16, which are
        # used to replace the 'presentValue' of an object. So, for the points that are 'inputs' in BOPtest, we created those as
        # commandable objects, so check to see if there is a higher priority value set for this object that is overwriting
        # what we should normally use - and if so, turn on the '_activate' signal for that point as well
        #
        # (BACpypes automatically turns a write to presentValue into a write to the priority array) - e.g. a client that
        # does this from a client:
        # python samples/ReadWriteProperty.py
        # > write 10.0.2.7 analogValue:63 presentValue 310
        #
        # BACpypes-based servers will change that into a modification of priorityArray at priority 16
        #
        #
        for k,v in inputs.items():
            #print("k: %s %s %s" % (str(k), v._highest_priority_value(), type(v._highest_priority_value()[1])))
            signal = v._highest_priority_value()
            if signal[1]:
                if k == 'advance' and self.oncommand:
                    advance_counter = signal[0]
                else:
                    signals[k] = signal[0]

        # Advancing simulation if counter is higher than previous value
        # if oncommand == False the statement is always True

        if advance_counter > self.advance_counter:


            if _debug:
                _log.debug('Advancing one step ' + time.strftime("%H:%M:%S", time.localtime()))

            status, message, payload = controller.sim.advance(signals)
            if status != 200:
                print("Error response: %r" % (status,))
                return

            # turn the response string into a JSON object
            json_response_payload = payload

        # set the object values
        # We advance the simulation by x seconds at each call to the loop, but we don't update the external world
        # with those results until the NEXT call to this function.
        #
        # TODO: don't ACK BACnet writes until we get to here - instead, buffer the write request and send the ACKs later
        # don't worry about concurrency, last-writer-wins is fine, but be sure to send multiple acks, one to each writer
        global nextState
        if nextState:
            for k, v in nextState.items():
                if _debug and (advance_counter > self.advance_counter):
                    self._debug("    - k, v: %r, %r", k, v)

                if k in objects:
                    #objects[k]._set_value(v)
                    objects[k].presentValue = v

        if advance_counter > self.advance_counter:
            nextState = json_response_payload
            if _debug and (self.advance_counter > 0):
                _log.debug('Increasing counter to: %r', advance_counter)
            if self.oncommand:
                self.advance_counter = advance_counter
        elif abs(advance_counter - 0.0) < 1E-6:
            if _debug and (self.advance_counter > 0):
                _log.debug('Resetting counter to: %r', advance_counter)
            if self.oncommand:
                self.advance_counter = advance_counter


# BAC0 uses the ReadPropertyMultiple service so make that available
@bacpypes_debugging
class ReadPropertyMultipleApplication(
   BIPSimpleApplication,
   ReadWritePropertyMultipleServices,
   DeviceCommunicationControlServices,
   ):
   pass

@bacpypes_debugging
def main():
    global vendor_id, g

    parser = ConfigArgumentParser(description=__doc__)

    parser.add_argument('--app_interval','-ai', type=str, default='5', help="Application refresh interval time in seconds, which triggers simulation advancement and data exchange. Using value 'oncommand' will give user control of refresh upon incrementing a positive integer value of an additional new BACnet point named 'advance'.")
    parser.add_argument('--control_step','-s', type=str, default='5', help="Simulation advance time step in seconds, with each application refresh.")

    # parse the command line arguments
    args = parser.parse_args()
    control_step = float(args.control_step)

    if "oncommand" in args.app_interval:
        oncommand = True
        APPINTERVAL = 100
    else:
        oncommand = False
        APPINTERVAL = float(args.app_interval)*1000
        if (APPINTERVAL/1000 < 0.5):
            _log.warning("WARNING: application refresh interval is less than 0.5 seconds, this may not be enough time for simulation to advance by one timestep")

    if _debug:
        _log.debug("initialization")
    if _debug:
        _log.debug("    - args: %r", args)

    # TODO: check the results to make sure we acutally get an OK!
    #
    global nextState, controller
    
    from .simulation_device import SimulationDevice
    # Set paths relative to this file's location
    SRC_FOLDER = Path(__file__).resolve().parent.parent.parent
    PROJECT_ROOT = SRC_FOLDER.parent
    
    # Convert string paths to Path objects if provided
    global_config_path_obj = None
    test_config_path_obj = None
    
    # Load configuration from global and test-specific files
    config = load_config(
        PROJECT_ROOT,
        global_config_path=global_config_path_obj,
        test_config_path=test_config_path_obj,
        force_device='simulation'
    )
    
    # Extract config sections
    device_config = config['device']

    controller = SimulationDevice(device_config=device_config)

    status, message, payload = controller.sim.initialize(0) 
    print(payload)
    nextState = payload

    global boptest_measurements, boptest_inputs
    boptest_measurements = controller.sim.output_names
    boptest_inputs = controller.sim.input_names
    # We advance the simulation by "control_step" seconds at each call to /advance.
    # if "APPINTERVAL" == "control_step" the simulation moves in sync with wallclock time.
    # To see things happen faster, set "control_step" > "APPINTERVAL"
    status, message, payload = controller.sim.set_step(control_step)

    # make a device object
    this_device = LocalDeviceObject(ini=args.ini)
    print(args.ini)
    if _debug:
        _log.debug("    - this_device: %r", this_device)

    # make a sample application
    this_application = ReadPropertyMultipleApplication(this_device, args.ini.address)

    file_name = 'conformance_tests/{0}/config/{0}.ttl'.format(config['test_type'])
    create_objects(this_application, file_name, oncommand)

    # run this update when the stack is ready
    if _debug:
        _log.debug('Start simulation ' + time.strftime("%H:%M:%S", time.localtime()))
    updater = BOPTESTUpdater(APPINTERVAL, oncommand)

    if _debug:
        _log.debug("    - updater: %r", updater)

    if _debug:
        _log.debug("running")

    run()

    if _debug:
        _log.debug("fini")


if __name__ == "__main__":
    main()
