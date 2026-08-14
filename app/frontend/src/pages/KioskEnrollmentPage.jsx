import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { kioskApi } from "../lib/kioskApi.js";

export default function KioskEnrollmentPage() {
  const navigate = useNavigate();
  const [values, setValues] = useState({
    code: "",
    display_name: "TalkBox kiosk",
    location: "",
    device_code: "",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function update(event) {
    setValues((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function submit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await kioskApi.enrollDevice({
        ...values,
        location: values.location || null,
        device_code: values.device_code || null,
      });
      navigate("/kiosk", { replace: true });
    } catch (requestError) {
      setError(requestError.message || "Enrollment could not be completed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-background px-4 py-8 text-foreground">
      <form onSubmit={submit} className="w-full max-w-lg border border-border bg-card p-6 shadow-sm">
        <p className="text-sm font-bold uppercase text-primary">TalkBox technician setup</p>
        <h1 className="mt-1 text-2xl font-bold">Enroll this kiosk</h1>
        <p className="mt-2 text-base text-muted-foreground">Enter the enrollment code supplied by a TalkBox administrator.</p>
        <label className="mt-6 grid gap-1 text-base font-semibold">Enrollment code
          <input required name="code" value={values.code} onChange={update} autoComplete="off" className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
        </label>
        <label className="mt-3 grid gap-1 text-base font-semibold">Kiosk name
          <input required name="display_name" value={values.display_name} onChange={update} className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
        </label>
        <label className="mt-3 grid gap-1 text-base font-semibold">Location
          <input name="location" value={values.location} onChange={update} className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
        </label>
        <label className="mt-3 grid gap-1 text-base font-semibold">Device code <span className="font-normal text-muted-foreground">(optional)</span>
          <input name="device_code" value={values.device_code} onChange={update} placeholder="TB-001" className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
        </label>
        {error ? <p className="mt-4 text-base text-destructive">{error}</p> : null}
        <div className="mt-6 flex items-center justify-between gap-3">
          <Link to="/kiosk" className="text-base font-semibold text-muted-foreground hover:text-foreground">Back to kiosk</Link>
          <button type="submit" disabled={submitting} className="h-10 rounded-md bg-primary px-4 font-semibold text-primary-foreground disabled:opacity-60">
            {submitting ? "Enrolling..." : "Enroll kiosk"}
          </button>
        </div>
      </form>
    </main>
  );
}