# -*- coding: utf-8 -*-
"""
This code is a modified version of bacnet/create_ttl.py from BOPTEST and is modified according to the license below,
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

Creates ttl file for creation of Brick objects.

To run this script:
1. Specify point map file
2. Run script
3. ''<test_case_name>.ttl'' file will be generated with inputs and measurement
   bacnet points

"""

import pandas as pd

# Read point map CSV (skip first 3 header rows, use 'Variable Name' as index)
df_pointmap = pd.read_csv('pointmap-foo-units.csv', header=3, index_col='Variable Name')

# Track output and parameter names for FMU initialization
output_names = []
parameter_names = []
points = []
# Process each point and create Point objects
advance = {'name':'advance', 'causality':None}
points.append(advance)
time = {'name':'time', 'causality':None}
points.append(time)

for test_name in df_pointmap.index:
    if not isinstance(test_name, str):
        continue
        
    row = df_pointmap.loc[test_name]
    causality = row['CDL Causality']
    cdl_block = row['CDL Block']
    cdl_name = row['CDL Name']
    cdl_type = row['CDL Type']
    cdl_unit = row['CDL Unit']
    unit = row['Unit']
    
    # Determine CDL path based on causality
    if causality == 'Input':
        cdl_path = cdl_name
    elif causality == 'Parameter':
        if cdl_block == '.':
            cdl_path = f"{cdl_name}"
        else:
            cdl_path = f"{cdl_block}.{cdl_name}"
        parameter_names.append(cdl_path)
    elif causality in ['Output', 'State']:
        if cdl_block == '.':
            cdl_path = f"{cdl_name}"
        else:
            cdl_path = f"{cdl_block}.{cdl_name}"
        output_names.append(cdl_path)
    else:
        continue
    
    # Create Point object
    point = {
        'name':cdl_path,
        'name_in_test':test_name,
        'unit_in_test':unit,
        'unit_in_device':cdl_unit,
        'point_type':cdl_type,
        'causality':causality,
        'metadata':{
            'cdl_block': cdl_block,
            'cdl_name': cdl_name
        }
    }
    
    
    points.append(point)

# Write the file prefix
prefix = '@prefix bldg: <urn:example#> .\n\
@prefix brick: <https://brickschema.org/schema/Brick#> .\n\
@prefix bacnet: <http://data.ashrae.org/bacnet/2020#> .\n\
@prefix unit: <http://qudt.org/vocab/unit/> .\n\
@prefix owl: <http://www.w3.org/2002/07/owl#> .\n\
@prefix ref: <https://brickschema.org/schema/Brick/ref#> .\n\
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n\
<urn:example#> a owl:Ontology ;\n\
\towl:imports <https://brickschema.org/schema/1.2/Brick#> .\n\n\
bldg:boptest-proxy-device a bacnet:BACnetDevice ;\n\
\tbacnet:device-instance 599 .\n\n'

with open('foo'+'.ttl', 'w') as f:
    f.write(prefix)


# Write the bacnet objects for each point in the file
with open('foo'+'.ttl', 'a') as f:
    obj_id = 1
    for point in points:
        # Assign type
        if point['causality'] == 'Output' or point['causality'] == 'State':
            obj_type = 'analog-input'
        elif point['causality'] == 'Input' or point['causality'] == 'Parameter' or point['name'] == 'advance':
            obj_type = 'analog-output'
        elif point['name'] == 'time':
            obj_type = 'analog-value'
        else:
            raise ValueError('{0} does not have a valid point causality of'.format(point['name'], point['causality']))

        f.write('bldg:{0} a brick:Point ;\n'.format(point['name']))
        f.write('\tref:hasExternalReference [\n')
        f.write('\t\tbacnet:object-identifier "{0},{1}" ;\n'.format(obj_type, obj_id))
        f.write('\t\tbacnet:object-type "{0}" ;\n'.format(obj_type))
        f.write('\t\tbacnet:object-name "{0}" ;\n'.format(point['name']))
        f.write('\t\tbacnet:status-flags 0 ;\n')
        f.write('\t\tbacnet:objectOf bldg:copper-proxy-device\n')
        f.write('\t] .\n\n')

        obj_id = obj_id + 1
