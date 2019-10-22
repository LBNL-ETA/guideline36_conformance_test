# ASHRAE Guideline 36 conformance Test

<p align="justify">
The American Society of Heating, Refrigerating and Air-Conditioning Engineers (ASHRAE) has established a set of standardized high performance sequences of operation for Heating, Ventilation and Air Conditioning (HVAC) systems in buildings through their "Guideline 36". In order to achieve the intended performance, these sequences must be translated and programmed accurately in the Building Automation System (BAS) controllers. Standardizing these sequences will allow for a more efficient product delivery mechanism where the sequences are programmed and tested centrally by each manufacturer, and then distributed to their dealers/engineering contractors. This approach would minimize the need for each installer to re-interpret and program the sequences, reduces risk of errors, and reduces the time required for commissioning in the field. 
</p>

<p align="justify">
To achieve this goal, a performance validation method is needed to provide independent confirmation that each manufacturer has programmed the Guideline 36 sequences accurately. A standardized method of test would also avoid the need for manual interpretation (and the associated human variability) that is required with typical functional testing approaches by automating the inputs and the range of expected responses. This software "guideline36_conformance_test" has been developed to conduct standardized, repeatable and manufacturer independent tests to validate that a BAS controller has been programmed in conformance with Guideline 36. Manufacturers would provide the controller (or the control program) and the software would run a suite of tests by setting a set of inputs to the controller and verifying the output signals from the controller matches the expected output as set by Guideline 36.
</p>

## Installation Instructions

### Set up environment
Install python3

pip install -r requirements.txt

Save test script to `files/`

### Configuration
Copy `src/config_template.yaml` to `src/config.yaml` and fill in the necessary configuration information.

## Start the test
Reset the controller: `python3 src/Test.py --reset `

Run the test: `python3 src/Test.py`

## Copyright

guideline36_conformance_test Copyright (c) 2019, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Dept. of Energy).  All rights reserved.

If you have questions about your rights to use or distribute this software, please contact Berkeley Lab's Intellectual Property Office at IPO@lbl.gov.

NOTICE.  This Software was developed under funding from the U.S. Department of Energy and the U.S. Government consequently retains certain rights.  As such, the U.S. Government has been granted for itself and others acting on its behalf a paid-up, nonexclusive, irrevocable, worldwide license in the Software to reproduce, distribute copies to the public, prepare derivative works, and perform publicly and display publicly, and to permit other to do so.

## License

guideline36_conformance_test is available under the following [license](https://github.com/LBNL-ETA/guideline36_conformance_test/blob/master/LICENSE.txt).

## Development and contribution

You may report any issues with using the [Issues](https://github.com/LBNL-ETA/guideline36_conformance_test/issues) button.

Contributions in the form of Pull Requests are always welcome.
