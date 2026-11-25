// Create a text parameter DataFolder pointing to the generated data directory.
// Create a blank query named LoadCsv; paste this function into Advanced Editor.
(file as text, types as list) as table =>
let
    Source = Csv.Document(File.Contents(DataFolder & "/" & file), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, types, "en-US")
in Typed

// Create five separate blank queries with the indicated names and expressions.
// dim_date
LoadCsv("dim_date.csv", {{"day", type date}, {"year", Int64.Type}, {"month", Int64.Type}})
// dim_region
LoadCsv("dim_region.csv", {{"region_id", Int64.Type}, {"region", type text}})
// dim_service
LoadCsv("dim_service.csv", {{"service_id", Int64.Type}, {"service", type text}})
// fact_actual
LoadCsv("fact_actual.csv", {{"day", type date}, {"region_id", Int64.Type}, {"service_id", Int64.Type}, {"amount_cents", Int64.Type}})
// fact_budget
LoadCsv("fact_budget.csv", {{"day", type date}, {"region_id", Int64.Type}, {"service_id", Int64.Type}, {"amount_cents", Int64.Type}})
