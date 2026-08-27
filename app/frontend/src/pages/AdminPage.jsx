import { useEffect, useRef, useState } from "react";
import { Download, Eye, EyeOff, LogOut, Pencil, Plus, Radio, Search, Trash2, Upload, XCircle } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api.js";
import { Button } from "../components/ui/Button.jsx";

const EMPTY_AGENCY = {
  agency: "",
  phone_number: "",
  address: "",
  categories: [],
  description: "",
  insurance: "",
  knowledge_tags: "",
  show_on_kiosk: true,
};

function errorMessage(error) {
  const detail = error?.data?.detail ?? error?.message;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail.map((item) => item.msg).join(" ");
  return "Something went wrong. Please try again.";
}

function AgencyForm({ agency, categories, onCancel, onSave, saving }) {
  const [values, setValues] = useState(agency || EMPTY_AGENCY);
  const [categorySearch, setCategorySearch] = useState("");

  function update(event) {
    setValues((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function submit(event) {
    event.preventDefault();
    await onSave(values);
  }

  const selectedCategories = values.categories || [];
  const matchingCategories = categories.filter((category) =>
    category.name.toLowerCase().includes(categorySearch.trim().toLowerCase())
  );
  const normalizedSearch = categorySearch.trim();
  const canCreateCategory = normalizedSearch
    && !categories.some((category) => category.name.toLowerCase() === normalizedSearch.toLowerCase())
    && !selectedCategories.some((category) => category.toLowerCase() === normalizedSearch.toLowerCase());

  function toggleCategory(name) {
    setValues((current) => ({
      ...current,
      categories: current.categories?.includes(name)
        ? current.categories.filter((category) => category !== name)
        : [...(current.categories || []), name],
    }));
  }

  return (
    <form onSubmit={submit} className="grid gap-3 border-b border-border bg-secondary/35 p-4 sm:grid-cols-2">
      <label className="grid gap-1 text-base font-semibold">Organization
        <input required name="agency" value={values.agency} onChange={update} className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
      </label>
      <label className="grid gap-1 text-base font-semibold">Phone
        <input name="phone_number" value={values.phone_number || ""} onChange={update} className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
      </label>
      <label className="grid gap-1 text-base font-semibold sm:col-span-2">Categories
        <input value={categorySearch} onChange={(event) => setCategorySearch(event.target.value)} placeholder="Search or add a category" className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
        {canCreateCategory ? <Button type="button" variant="outline" className="mt-2 self-start" onClick={() => { toggleCategory(normalizedSearch); setCategorySearch(""); }}>Add “{normalizedSearch}”</Button> : null}
        <div className="mt-2 grid max-h-44 grid-cols-1 gap-1 overflow-y-auto rounded-md border border-input bg-background p-2 sm:grid-cols-2">
          {matchingCategories.map((category) => <label key={category.id} className="flex items-center gap-2 rounded px-2 py-1 font-normal hover:bg-secondary">
            <input type="checkbox" checked={selectedCategories.includes(category.name)} onChange={() => toggleCategory(category.name)} className="h-4 w-4 accent-primary" />
            {category.name}
          </label>)}
          {!matchingCategories.length && !canCreateCategory ? <p className="px-2 py-1 font-normal text-muted-foreground">No matching categories.</p> : null}
        </div>
        {selectedCategories.length ? <div className="mt-2 flex flex-wrap gap-1">{selectedCategories.map((category) => <button key={category} type="button" onClick={() => toggleCategory(category)} className="rounded-full bg-primary/10 px-2 py-1 text-sm font-normal text-primary">{category} ×</button>)}</div> : <p className="mt-1 font-normal text-muted-foreground">Select every category this resource serves.</p>}
      </label>
      <label className="grid gap-1 text-base font-semibold">Insurance
        <input name="insurance" value={values.insurance || ""} onChange={update} className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
      </label>
      <label className="grid gap-1 text-base font-semibold sm:col-span-2">Address
        <input name="address" value={values.address || ""} onChange={update} className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
      </label>
      <label className="grid gap-1 text-base font-semibold sm:col-span-2">Services
        <textarea name="description" value={values.description || ""} onChange={update} rows="2" className="rounded-md border border-input bg-background p-3 font-normal" />
      </label>
      <label className="grid gap-1 text-base font-semibold sm:col-span-2">Tags
        <input name="knowledge_tags" value={values.knowledge_tags || ""} onChange={update} className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
      </label>
      <label className="flex items-center gap-3 rounded-md border border-input bg-background p-3 text-base font-semibold sm:col-span-2">
        <input
          type="checkbox"
          name="show_on_kiosk"
          checked={values.show_on_kiosk !== false}
          onChange={(event) => setValues((current) => ({ ...current, show_on_kiosk: event.target.checked }))}
          className="h-5 w-5 accent-primary"
        />
        <span>Show in kiosk Browse directory
          <span className="block font-normal text-muted-foreground">Hidden resources remain available to voice search.</span>
        </span>
      </label>
      <div className="flex justify-end gap-2 sm:col-span-2">
        <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
        <Button type="submit" disabled={saving}>{saving ? "Saving..." : "Save resource"}</Button>
      </div>
    </form>
  );
}

function LoginGate({ onLoggedIn }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setPending(true);
    try {
      await api.admin.login(email, password);
      await api.admin.currentUser();
      await onLoggedIn();
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto grid min-h-screen max-w-md place-items-center px-4">
      <form onSubmit={submit} className="w-full border border-border bg-card p-6 shadow-sm">
        <p className="text-base font-bold uppercase text-primary">TalkBox operations</p>
        <h1 className="mt-1 text-2xl font-bold">Resource manager</h1>
        <p className="mt-2 text-base text-muted-foreground">Sign in with the administrator account to manage live resources.</p>
        <label className="mt-6 grid gap-1 text-base font-semibold">Email
          <input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
        </label>
        <label className="mt-3 grid gap-1 text-base font-semibold">Password
          <input required type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
        </label>
        <Button className="mt-6 w-full" type="submit" disabled={pending}>{pending ? "Signing in..." : "Sign in"}</Button>
      </form>
    </main>
  );
}

function KioskFleetPanel({ devices, enrollmentCode, onCreateCode, onUpdateDevice }) {
  return (
    <section className="mt-5 border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
        <div>
          <h2 className="font-bold">Kiosk devices</h2>
          <p className="text-base text-muted-foreground">Enroll tablets and revoke their calling access.</p>
        </div>
        <Button onClick={onCreateCode}><Plus className="mr-2 h-4 w-4" />Create enrollment code</Button>
      </div>
      {enrollmentCode ? <div className="border-b border-border bg-primary/5 p-4">
        <p className="font-semibold">New code, shown once</p>
        <code className="mt-1 block break-all rounded bg-background p-2 text-base">{enrollmentCode.code}</code>
        <p className="mt-2 text-base text-muted-foreground">Expires {new Date(enrollmentCode.expires_at).toLocaleString()}.</p>
      </div> : null}
      <div className="overflow-x-auto">
        <table className="w-full min-w-180 text-left text-base">
          <thead className="border-b border-border bg-secondary/50 text-muted-foreground"><tr>
            <th className="px-4 py-3 font-semibold">Code</th><th className="px-4 py-3 font-semibold">Name</th><th className="px-4 py-3 font-semibold">Location</th><th className="px-4 py-3 font-semibold">Status</th><th className="px-4 py-3 font-semibold">Last seen</th><th className="w-28 px-4 py-3"><span className="sr-only">Actions</span></th>
          </tr></thead>
          <tbody>{devices.map((device) => <tr key={device.id} className="border-b border-border last:border-0">
            <td className="px-4 py-3 font-semibold">{device.device_code}</td><td className="px-4 py-3">{device.display_name}</td><td className="px-4 py-3">{device.location || "-"}</td>
            <td className="px-4 py-3">{device.revoked_at ? "Revoked" : device.enabled ? "Enabled" : "Disabled"}</td><td className="px-4 py-3">{device.last_seen_at ? new Date(device.last_seen_at).toLocaleString() : "Never"}</td>
            <td className="px-4 py-3"><div className="flex justify-end gap-1">
              {!device.revoked_at ? <Button size="icon" variant="ghost" title="Revoke device" aria-label={`Revoke ${device.device_code}`} onClick={() => onUpdateDevice(device, { revoke: true })}><XCircle className="h-4 w-4 text-destructive" /></Button> : null}
              {!device.revoked_at ? <Button size="sm" variant="outline" onClick={() => onUpdateDevice(device, { enabled: !device.enabled })}>{device.enabled ? "Disable" : "Enable"}</Button> : null}
            </div></td>
          </tr>)}</tbody>
        </table>
      </div>
      {!devices.length ? <p className="p-6 text-center text-muted-foreground">No kiosks enrolled yet.</p> : null}
    </section>
  );
}

export default function AdminPage() {
  const [authenticated, setAuthenticated] = useState(null);
  const sessionCheckId = useRef(0);
  const [resources, setResources] = useState({ items: [], total: 0, visible_total: 0, page: 1, page_size: 25 });
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewRows, setPreviewRows] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const [bulkCategories, setBulkCategories] = useState([]);
  const [bulkCategorySearch, setBulkCategorySearch] = useState("");
  const [bulkSaving, setBulkSaving] = useState(false);
  const [devices, setDevices] = useState([]);
  const [enrollmentCode, setEnrollmentCode] = useState(null);
  const [pushing, setPushing] = useState(false);

  async function checkSession() {
    const checkId = ++sessionCheckId.current;
    try {
      await api.admin.currentUser();
      if (checkId === sessionCheckId.current) setAuthenticated(true);
    } catch {
      if (checkId === sessionCheckId.current) setAuthenticated(false);
    }
  }

  async function loadResources() {
    try {
      const [agencyPage, categoryList] = await Promise.all([
        api.admin.agencies({ search, category, page }),
        api.admin.categories(),
      ]);
      setResources(agencyPage);
      setCategories(categoryList);
      setSelectedIds((current) => current.filter((id) => agencyPage.items.some((item) => item.id === id)));
    } catch (error) {
      if (error.status === 401 || error.status === 403) setAuthenticated(false);
      else toast.error(errorMessage(error));
    }
  }

  async function loadDevices() {
    try {
      setDevices(await api.admin.devices());
    } catch (error) {
      if (error.status === 401 || error.status === 403) setAuthenticated(false);
      else toast.error(errorMessage(error));
    }
  }

  useEffect(() => { checkSession(); }, []);
  useEffect(() => {
    if (authenticated) loadResources();
  }, [authenticated, search, category, page]);
  useEffect(() => {
    if (authenticated) loadDevices();
  }, [authenticated]);

  async function createEnrollmentCode() {
    try {
      setEnrollmentCode(await api.admin.createDeviceEnrollmentCode());
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  async function updateDevice(device, changes) {
    const action = changes.revoke ? "revoke" : changes.enabled ? "enable" : "disable";
    if (changes.revoke && !window.confirm(`Revoke ${device.device_code}? It will lose calling access immediately.`)) return;
    try {
      await api.admin.updateDevice(device.id, changes);
      await loadDevices();
      toast.success(`${device.device_code} ${action}d.`);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  async function saveAgency(values) {
    setSaving(true);
    try {
      if (editing?.id) await api.admin.updateAgency(editing.id, values);
      else await api.admin.createAgency(values);
      setEditing(null);
      await loadResources();
      toast.success("Resource saved.");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function removeAgency(agency) {
    if (!window.confirm(`Delete ${agency.agency}?`)) return;
    try {
      await api.admin.deleteAgency(agency.id);
      await loadResources();
      toast.success("Resource deleted.");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  async function toggleVisibility(agency) {
    try {
      await api.admin.updateAgency(agency.id, {
        ...agency,
        show_on_kiosk: agency.show_on_kiosk === false,
      });
      await loadResources();
      toast.success(agency.show_on_kiosk === false ? "Resource shown in Browse." : "Resource hidden from Browse.");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  function toggleSelected(id) {
    setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  function toggleBulkCategory(name) {
    setBulkCategories((current) => current.includes(name) ? current.filter((item) => item !== name) : [...current, name]);
  }

  async function applyBulkChanges(changes, message) {
    if (!selectedIds.length) return;
    setBulkSaving(true);
    try {
      const result = await api.admin.bulkUpdateAgencies({ ids: selectedIds, ...changes });
      setSelectedIds([]);
      setBulkCategories([]);
      await loadResources();
      toast.success(`${result.updated} resources ${message}.`);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBulkSaving(false);
    }
  }

  async function downloadExport() {
    try {
      const blob = await api.admin.exportAgencies();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "agencies_master.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  async function pushToKiosks() {
    setPushing(true);
    try {
      const result = await api.admin.pushToKiosks();
      toast.success(
        `Pushed catalog v${result.content_version} to kiosks (${result.visible_count} in Browse, ${result.agency_count} total).`
      );
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setPushing(false);
    }
  }

  async function logout() {
    try {
      await api.admin.logout();
    } finally {
      setAuthenticated(false);
    }
  }

  async function importFile(event) {
    const [file] = event.target.files;
    if (!file) return;
    setUploading(true);
    try {
      const createdPreview = await api.admin.previewImport(file);
      setPreview(createdPreview);
      setPreviewRows(createdPreview.invalid_rows ? await api.admin.importRows(createdPreview.id) : []);
      toast.success("Import preview is ready.");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function finalizeImport(action) {
    try {
      const result = action === "publish"
        ? await api.admin.publishImport(preview.id)
        : await api.admin.discardImport(preview.id);
      setPreview(result);
      if (action === "publish") await loadResources();
      toast.success(action === "publish" ? "Resources published." : "Preview discarded.");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  if (authenticated === null) return null;
  if (!authenticated) {
    return <LoginGate onLoggedIn={() => {
      sessionCheckId.current += 1;
      setAuthenticated(true);
    }} />;
  }

  const pages = Math.max(1, Math.ceil(resources.total / resources.page_size));
  return (
    <main className="min-h-screen bg-background px-4 py-6 text-foreground sm:px-6">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5">
          <div>
            <p className="text-base font-bold uppercase text-primary">TalkBox operations</p>
            <h1 className="mt-1 text-2xl font-bold">Resource manager</h1>
            <p className="mt-1 text-base text-muted-foreground">
              {resources.visible_total} shown in Browse · {resources.total} available to voice search
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={downloadExport}><Download className="mr-2 h-4 w-4" />Export CSV</Button>
            <Button variant="outline" onClick={pushToKiosks} disabled={pushing}>
              <Radio className="mr-2 h-4 w-4" />{pushing ? "Pushing..." : "Push to kiosks"}
            </Button>
            <label className="inline-flex h-10 cursor-pointer items-center rounded-md bg-primary px-4 text-base font-semibold text-primary-foreground hover:bg-primary/90">
              <Upload className="mr-2 h-4 w-4" />{uploading ? "Uploading..." : "Preview import"}
              <input className="sr-only" type="file" accept=".csv,.xlsx,.xlsm" onChange={importFile} disabled={uploading} />
            </label>
            <Button onClick={() => setEditing(EMPTY_AGENCY)}><Plus className="mr-2 h-4 w-4" />Add resource</Button>
            <Button variant="outline" onClick={logout}><LogOut className="mr-2 h-4 w-4" />Sign out</Button>
          </div>
        </header>

        {preview ? (
          <section className="mt-5 border border-border bg-secondary/40 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-bold">Import preview: {preview.filename}</h2>
                <p className="text-base text-muted-foreground">{preview.valid_rows} valid, {preview.invalid_rows} needing attention, {preview.total_rows} total rows.</p>
              </div>
              {preview.status === "previewed" ? <div className="flex gap-2">
                <Button variant="outline" onClick={() => finalizeImport("discard")}>Discard</Button>
                <Button disabled={preview.invalid_rows > 0 || preview.total_rows === 0} onClick={() => finalizeImport("publish")}>Publish live resources</Button>
              </div> : <span className="font-semibold text-muted-foreground">{preview.status}</span>}
            </div>
            {preview.errors?.map((error, index) => <p key={index} className="mt-2 text-base text-destructive">{error.message}</p>)}
            {previewRows.filter((row) => row.errors.length).slice(0, 8).map((row) => (
              <p key={row.row_number} className="mt-2 text-base text-destructive">Row {row.row_number}: {row.errors.join(" ")}</p>
            ))}
          </section>
        ) : null}

        <KioskFleetPanel
          devices={devices}
          enrollmentCode={enrollmentCode}
          onCreateCode={createEnrollmentCode}
          onUpdateDevice={updateDevice}
        />

        <section className="mt-5 border border-border bg-card">
          <div className="flex flex-wrap gap-3 border-b border-border p-4">
            <label className="relative min-w-56 flex-1"><Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search name, address, services" className="h-10 w-full rounded-md border border-input bg-background pl-9 pr-3" />
            </label>
            <select value={category} onChange={(event) => { setCategory(event.target.value); setPage(1); }} className="h-10 rounded-md border border-input bg-background px-3">
              <option value="">All categories</option>
              {categories.map((item) => <option key={item.id} value={item.name}>{item.name} ({item.agency_count})</option>)}
            </select>
          </div>
          {editing ? <AgencyForm agency={editing} categories={categories} saving={saving} onCancel={() => setEditing(null)} onSave={saveAgency} /> : null}
          {selectedIds.length ? <section className="flex flex-wrap items-center gap-3 border-b border-border bg-primary/5 p-4">
            <strong>{selectedIds.length} selected</strong>
            <Button size="sm" variant="outline" disabled={bulkSaving} onClick={() => applyBulkChanges({ show_on_kiosk: true }, "shown in Browse")}>Show in Browse</Button>
            <Button size="sm" variant="outline" disabled={bulkSaving} onClick={() => applyBulkChanges({ show_on_kiosk: false }, "hidden from Browse")}>Hide from Browse</Button>
            <label className="min-w-48 flex-1">Replace categories
              <input value={bulkCategorySearch} onChange={(event) => setBulkCategorySearch(event.target.value)} placeholder="Filter categories" className="ml-2 h-9 rounded-md border border-input bg-background px-2" />
            </label>
            <div className="flex max-w-full flex-wrap gap-1">{categories.filter((item) => item.name.toLowerCase().includes(bulkCategorySearch.toLowerCase())).map((item) => <label key={item.id} className="rounded bg-background px-2 py-1 text-sm"><input type="checkbox" checked={bulkCategories.includes(item.name)} onChange={() => toggleBulkCategory(item.name)} className="mr-1 accent-primary" />{item.name}</label>)}</div>
            <Button size="sm" disabled={bulkSaving} onClick={() => applyBulkChanges({ categories: bulkCategories }, "updated")}>Apply categories</Button>
            <Button size="sm" variant="ghost" disabled={bulkSaving} onClick={() => setSelectedIds([])}>Clear selection</Button>
          </section> : null}
          <div className="overflow-x-auto">
            <table className="w-full min-w-220 text-left text-base">
              <thead className="border-b border-border bg-secondary/50 text-muted-foreground"><tr>
                <th className="px-4 py-3"><input type="checkbox" aria-label="Select all resources on this page" checked={resources.items.length > 0 && resources.items.every((agency) => selectedIds.includes(agency.id))} onChange={(event) => setSelectedIds(event.target.checked ? resources.items.map((agency) => agency.id) : [])} /></th><th className="px-4 py-3 font-semibold">Organization</th><th className="px-4 py-3 font-semibold">Browse</th><th className="px-4 py-3 font-semibold">Categories</th><th className="px-4 py-3 font-semibold">Phone</th><th className="px-4 py-3 font-semibold">Address</th><th className="w-32 px-4 py-3"><span className="sr-only">Actions</span></th>
              </tr></thead>
              <tbody>{resources.items.map((agency) => <tr key={agency.id} className="border-b border-border last:border-0">
                <td className="px-4 py-3"><input type="checkbox" aria-label={`Select ${agency.agency}`} checked={selectedIds.includes(agency.id)} onChange={() => toggleSelected(agency.id)} /></td><td className="px-4 py-3 font-semibold">{agency.agency}<p className="mt-1 font-normal text-muted-foreground">{agency.description}</p></td>
                <td className="px-4 py-3"><Button size="icon" variant="ghost" title={agency.show_on_kiosk === false ? "Show in kiosk Browse" : "Hide from kiosk Browse"} aria-label={agency.show_on_kiosk === false ? "Show in kiosk Browse" : "Hide from kiosk Browse"} onClick={() => toggleVisibility(agency)}>{agency.show_on_kiosk === false ? <EyeOff className="h-4 w-4 text-muted-foreground" /> : <Eye className="h-4 w-4 text-primary" />}</Button></td>
                <td className="px-4 py-3">{agency.categories?.length ? <div className="flex flex-wrap gap-1">{agency.categories.map((item) => <span key={item} className="rounded-full bg-secondary px-2 py-1 text-sm">{item}</span>)}</div> : "Uncategorized"}</td><td className="px-4 py-3">{agency.phone_number || "-"}</td><td className="px-4 py-3">{agency.address || "-"}</td>
                <td className="px-4 py-3"><div className="flex justify-end gap-1"><Button size="icon" variant="ghost" title="Edit resource" aria-label="Edit resource" onClick={() => setEditing(agency)}><Pencil className="h-4 w-4" /></Button><Button size="icon" variant="ghost" title="Delete resource" aria-label="Delete resource" onClick={() => removeAgency(agency)}><Trash2 className="h-4 w-4 text-destructive" /></Button></div></td>
              </tr>)}</tbody>
            </table>
          </div>
          {!resources.items.length ? <p className="p-8 text-center text-muted-foreground">No matching resources.</p> : null}
          <footer className="flex items-center justify-between border-t border-border p-4 text-base"><span>Page {page} of {pages}</span><div className="flex gap-2"><Button variant="outline" disabled={page === 1} onClick={() => setPage((current) => current - 1)}>Previous</Button><Button variant="outline" disabled={page === pages} onClick={() => setPage((current) => current + 1)}>Next</Button></div></footer>
        </section>
      </div>
    </main>
  );
}