import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { SelectField } from "../components/Field";
import { PageHeader } from "../components/PageHeader";
import { DemandView } from "../dashboard/DemandSection";
import { MaintenanceView } from "../dashboard/MaintenanceSection";
import { OverdueView } from "../dashboard/OverdueSection";
import { PaymentsView } from "../dashboard/PaymentsSection";
import { ReportSection } from "../dashboard/ReportSection";
import { SummaryView } from "../dashboard/SummarySection";
import { UtilizationView } from "../dashboard/UtilizationSection";
import type { Bucket } from "../types";
import { useAsync } from "../useAsync";
import { useTitle } from "../useTitle";

/** The periods offered. The server accepts 1 to 366 days; these are the ones worth looking at. */
export const PERIOD_CHOICES = [7, 14, 30, 90];
const DEFAULT_DAYS = 30;

export default function DashboardPage() {
  useTitle("Dashboard");
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get("days"));
  const days = PERIOD_CHOICES.includes(requested) ? requested : DEFAULT_DAYS;
  const bucket: Bucket = params.get("bucket") === "week" ? "week" : "day";

  function change(name: "days" | "bucket", value: string) {
    const next = new URLSearchParams(params);
    next.set(name, value);
    setParams(next);
  }

  // Each report loads on its own, so one that fails shows its own error and the rest still work.
  const summary = useAsync(`summary:${days}`, (signal) => api.analyticsSummary(days, signal));
  const utilization = useAsync(`utilization:${days}:${bucket}`, (signal) =>
    api.analyticsUtilization(days, bucket, signal),
  );
  const demand = useAsync(`demand:${days}`, (signal) => api.analyticsDemand(days, signal));
  const overdue = useAsync(`overdue-aging:${days}`, (signal) =>
    api.analyticsOverdueAging(days, signal),
  );
  const payments = useAsync(`payments:${days}:${bucket}`, (signal) =>
    api.analyticsPayments(days, bucket, signal),
  );
  const maintenance = useAsync("maintenance", (signal) => api.analyticsMaintenance(signal));

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Figures come straight from the rental records. Money is in rupees (₹) and dates are in Indian Standard Time (IST). Every period runs up to now, so today counts as a part-day."
      />

      <div className="controls-bar">
        <form className="dashboard-controls" onSubmit={(event) => event.preventDefault()}>
          <SelectField
            label="Period"
            value={String(days)}
            onChange={(event) => change("days", event.target.value)}
          >
            {PERIOD_CHOICES.map((choice) => (
              <option key={choice} value={choice}>
                Last {choice} days
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Group charts by"
            value={bucket}
            onChange={(event) => change("bucket", event.target.value)}
          >
            <option value="day">Day</option>
            <option value="week">Week (Monday to Sunday)</option>
          </SelectField>
        </form>

        <nav className="jump" aria-label="Dashboard sections">
          <a href="#summary-heading">Summary</a>
          <a href="#utilization-heading">Utilization</a>
          <a href="#demand-heading">Demand</a>
          <a href="#overdue-heading">Overdue</a>
          <a href="#payments-heading">Payments</a>
          <a href="#maintenance-heading">Maintenance</a>
        </nav>
      </div>

      <ReportSection id="summary" title="Summary" what="the summary" state={summary} icon="chart">
        {(data) => <SummaryView data={data} />}
      </ReportSection>
      <ReportSection
        id="utilization"
        title="Utilization"
        what="utilization"
        state={utilization}
        icon="box"
      >
        {(data) => <UtilizationView data={data} />}
      </ReportSection>
      <ReportSection id="demand" title="Demand" what="demand" state={demand} icon="funnel">
        {(data) => <DemandView data={data} />}
      </ReportSection>
      <ReportSection
        id="overdue"
        title="Overdue loans"
        what="overdue loans"
        state={overdue}
        icon="clock"
      >
        {(data) => <OverdueView data={data} />}
      </ReportSection>
      <ReportSection id="payments" title="Payments" what="payments" state={payments} icon="rupee">
        {(data) => <PaymentsView data={data} />}
      </ReportSection>
      <ReportSection
        id="maintenance"
        title="Maintenance snapshot"
        what="maintenance"
        state={maintenance}
        icon="wrench"
      >
        {(data) => <MaintenanceView data={data} />}
      </ReportSection>
    </>
  );
}
