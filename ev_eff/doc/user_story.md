**Annual Vehicle Efficiency Report - MyEicher Portal**

*Key details*

*Description*
This User Story is created to add a new Annual Vehicle Efficiency Report in MyEicher Portal under Our Services → Fleet Monitoring → Reports. The report will provide annual EV fleet efficiency in kWh/km, month-wise efficiency trend, vehicle-wise annual efficiency, underperforming status, top indicator, and Excel/PDF export functionality. Please refer to the attached BRD for detailed logic and UI behaviour.

Acceptance Criteria:

Annual Vehicle Efficiency Report shall be added under Our Services → Fleet Monitoring → Reports.

Report shall auto-load for the latest 12 completed months with no date/duration filter.

Summary cards shall show:

Vehicles Operated

Total Distance Travelled

Total Power Consumption

Fleet Vehicle Efficiency

Month-wise bar graph shall show fleet-level monthly kWh/km by default.

When a vehicle number is searched, the selected vehicle filter shall apply across KPI cards, graph, table, and export.

Vehicle-wise table shall show Vehicle No., Chassis No., Model, Distance, TPC, kWh/km, Deviation, Status, and Top Indicator.

Status and Top Indicator filters shall be available for the vehicle-wise table.

Underperforming logic shall be calculated in backend using same model/segment comparison for mixed fleets.

Top Indicator shall support High AC Load, Driving Behaviour, Data Review Required, and No Major Indicator.

Excel and PDF export shall be available and should follow existing MyEicher export format.

Report data shall be sourced from the Primary Daily Aggregate Table.

Clearing the vehicle search shall reset the page to default All Vehicles view.

Figma Link:
Annual Vehicle Efficiency Report

Attachments:
Annual Vehicle Efficiency Report BRD - MyEicher Portal.
