within ;
model testscript_foo_units_fmu
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u1 annotation (Placement(
        transformation(extent={{-120,90},{-100,110}}), iconTransformation(
          extent={{-120,90},{-100,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u2 annotation (Placement(
        transformation(extent={{-120,70},{-100,90}}), iconTransformation(extent
          ={{-120,80},{-100,100}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u3 annotation (Placement(
        transformation(extent={{-120,50},{-100,70}}), iconTransformation(extent
          ={{-120,90},{-100,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u4 annotation (Placement(
        transformation(extent={{-120,30},{-100,50}}), iconTransformation(extent
          ={{-120,80},{-100,100}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u5 annotation (Placement(
        transformation(extent={{-120,10},{-100,30}}), iconTransformation(extent
          ={{-120,90},{-100,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u6 annotation (Placement(
        transformation(extent={{-120,-10},{-100,10}}), iconTransformation(
          extent={{-120,80},{-100,100}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u7 annotation (Placement(
        transformation(extent={{-120,-30},{-100,-10}}), iconTransformation(
          extent={{-120,90},{-100,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u8 annotation (Placement(
        transformation(extent={{-120,-50},{-100,-30}}), iconTransformation(
          extent={{-120,80},{-100,100}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u9 annotation (Placement(
        transformation(extent={{-120,-70},{-100,-50}}), iconTransformation(
          extent={{-120,90},{-100,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u10 annotation (Placement(
        transformation(extent={{-120,-90},{-100,-70}}), iconTransformation(
          extent={{-120,80},{-100,100}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u11 annotation (Placement(
        transformation(extent={{-120,-110},{-100,-90}}), iconTransformation(
          extent={{-120,90},{-100,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealOutput cdl_y1 annotation (Placement(
        transformation(extent={{-80,90},{-60,110}}), iconTransformation(extent=
            {{-80,90},{-60,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealOutput cdl_y2 annotation (Placement(
        transformation(extent={{-80,70},{-60,90}}), iconTransformation(extent={
            {100,90},{120,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealOutput cdl_y3 annotation (Placement(
        transformation(extent={{-80,50},{-60,70}}), iconTransformation(extent={
            {100,90},{120,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealOutput cdl_y4 annotation (Placement(
        transformation(extent={{-80,30},{-60,50}}), iconTransformation(extent={
            {100,90},{120,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealOutput cdl_y5 annotation (Placement(
        transformation(extent={{-80,10},{-60,30}}), iconTransformation(extent={
            {100,90},{120,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealOutput cdl_y6 annotation (Placement(
        transformation(extent={{-80,-10},{-60,10}}), iconTransformation(extent=
            {{100,90},{120,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealOutput cdl_y7 annotation (Placement(
        transformation(extent={{-80,-30},{-60,-10}}), iconTransformation(extent
          ={{100,90},{120,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealOutput cdl_y8 annotation (Placement(
        transformation(extent={{-80,-50},{-60,-30}}), iconTransformation(extent
          ={{100,90},{120,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealOutput cdl_y9 annotation (Placement(
        transformation(extent={{-80,-70},{-60,-50}}), iconTransformation(extent
          ={{100,90},{120,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealOutput cdl_y10 annotation (
      Placement(transformation(extent={{-80,-90},{-60,-70}}),
        iconTransformation(extent={{100,90},{120,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealOutput cdl_y11 annotation (
      Placement(transformation(extent={{-80,-110},{-60,-90}}),
        iconTransformation(extent={{100,90},{120,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u12 annotation (Placement(
        transformation(extent={{-40,90},{-20,110}}),     iconTransformation(
          extent={{-120,90},{-100,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u13 annotation (Placement(
        transformation(extent={{-40,70},{-20,90}}),      iconTransformation(
          extent={{-120,90},{-100,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u14 annotation (Placement(
        transformation(extent={{-40,50},{-20,70}}),      iconTransformation(
          extent={{-120,90},{-100,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u15 annotation (Placement(
        transformation(extent={{-40,30},{-20,50}}),      iconTransformation(
          extent={{-120,90},{-100,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u16 annotation (Placement(
        transformation(extent={{-40,10},{-20,30}}),      iconTransformation(
          extent={{-120,90},{-100,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u17 annotation (Placement(
        transformation(extent={{-40,-10},{-20,10}}),     iconTransformation(
          extent={{-120,90},{-100,110}})));
  Buildings.Controls.OBC.CDL.Interfaces.RealInput cdl_u18 annotation (Placement(
        transformation(extent={{-40,-30},{-20,-10}}),    iconTransformation(
          extent={{-120,90},{-100,110}})));
equation
  // Check that 69.6 F is within 0.5 F of 70 F, in K
  cdl_y6 = cdl_u6 - 0.2221;
  // Check that 504 cfm is within 5 cfm of 500 cfm, in m3/s
  cdl_y7 = cdl_u7 + 0.00189;
  // Check that 804 ppm is within 5 ppm of 800 ppm, in ppm
  cdl_y8 = cdl_u8 + 4;
  // Check that 56 % is within 5 % of 60 %, in 1
  cdl_y9 = cdl_u9 - 0.04;
  // Check that 204 gpm is within 5 gpm of 200 gpm, in m3/s
  cdl_y10 = cdl_u10 + 0.00027;
  // Check that 4.05 dF is within 0.1 dF of 4 dF, in dK
  cdl_y11 = cdl_u11 + 0.02811;
  connect(cdl_u1, cdl_y1)
    annotation (Line(points={{-110,100},{-70,100}}, color={0,0,127}));
  connect(cdl_u2, cdl_y2)
    annotation (Line(points={{-110,80},{-70,80}}, color={0,0,127}));
  connect(cdl_u3, cdl_y3)
    annotation (Line(points={{-110,60},{-70,60}}, color={0,0,127}));
  connect(cdl_u4, cdl_y4)
    annotation (Line(points={{-110,40},{-70,40}}, color={0,0,127}));
  connect(cdl_u5, cdl_y5)
    annotation (Line(points={{-110,20},{-70,20}}, color={0,0,127}));
  annotation (uses(Buildings(version="11.0.0")));
end testscript_foo_units_fmu;
