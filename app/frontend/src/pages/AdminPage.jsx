import { useEffect, useState } from "react";
import { Download, FileUp, Pencil, Plus, Search, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api.js";
import { Button } from "../components/ui/Button.jsx";

const EMPTY_AGENCY = {
  agency: "",
  phone_number: "",
  address: "",
  category: "",
  description: "",
  insurance: "",
  knowledge_tags: "",
};

function errorMessage(error) {
  return error?.message || "Something went wrong. Please try again.";
}

function AgencyForm({ agency, onCancel, onSave, saving }) {
  const [values, setValues] = useState(agency || EMPTY_AGENCY);

  function update(event) {
    setValues((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function submit(event) {
    event.preventDefault();
    await onSave(values);
  }

  return (
    <form onSubmit={submit} className="grid gap-3 border-b border-border bg-secondary/35 p-4 sm:grid-cols-2">
      <label className="grid gap-1 text-base font-semibold">Organization
        <input required name="agency" value={values.agency} onChange={update} className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
      </label>
      <label className="grid gap-1 text-base font-semibold">Phone
        <input name="phone_number" value={values.phone_number || ""} onChange={update} className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
      </label>
      <label className="grid gap-1 text-base font-semibold">Category
        <input name="category" value={values.category || ""} onChange={update} className="h-10 rounded-md border border-input bg-background px-3 font-normal" />
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

export default function AdminPage() {
  const [authenticated, setAuthenticated] = useState(null);
  const [resources, setResources] = useState({ items: [], total: 0, page: 1, page_size: 25 });
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewRows, setPreviewRows] = useState([]);
  const [uploading, setUploading] = useState(false);

  async function checkSession() {
    try {
      await api.admin.currentUser();
      setAuthenticated(true);
    } catch {
      setAuthenticated(false);
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
    } catch (error) {
      if (error.status === 401 || error.status === 403) setAuthenticated(false);
      else toast.error(errorMessage(error));
    }
  }

  useEffect(() => { checkSession(); }, []);
  useEffect(() => {
    if (authenticated) loadResources();
  }, [authenticated, search, category, page]);

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
  if (!authenticated) return <LoginGate onLoggedIn={checkSession} />;

  const pages = Math.max(1, Math.ceil(resources.total / resources.page_size));
  return (
    <main className="min-h-screen bg-background px-4 py-6 text-foreground sm:px-6">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5">
          <div>
            <p className="text-base font-bold uppercase text-primary">TalkBox operations</p>
            <h1 className="mt-1 text-2xl font-bold">Resource manager</h1>
            <p className="mt-1 text-base text-muted-foreground">{resources.total} live resources available to TalkBox.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a href={api.admin.exportUrl()}><Button variant="outline"><Download className="mr-2 h-4 w-4" />Export CSV</Button></a>
            <label className="inline-flex h-10 cursor-pointer items-center rounded-md bg-primary px-4 text-base font-semibold text-primary-foreground hover:bg-primary/90">
              <Upload className="mr-2 h-4 w-4" />{uploading ? "Uploading..." : "Preview import"}
              <input className="sr-only" type="file" accept=".csv,.xlsx,.xlsm" onChange={importFile} disabled={uploading} />
            </label>
            <Button onClick={() => setEditing(EMPTY_AGENCY)}><Plus className="mr-2 h-4 w-4" />Add resource</Button>
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
          {editing ? <AgencyForm agency={editing} saving={saving} onCancel={() => setEditing(null)} onSave={saveAgency} /> : null}
          <div className="overflow-x-auto">
            <table className="w-full min-w-220 text-left text-base">
              <thead className="border-b border-border bg-secondary/50 text-muted-foreground"><tr>
                <th className="px-4 py-3 font-semibold">Organization</th><th className="px-4 py-3 font-semibold">Category</th><th className="px-4 py-3 font-semibold">Phone</th><th className="px-4 py-3 font-semibold">Address</th><th className="w-24 px-4 py-3"><span className="sr-only">Actions</span></th>
              </tr></thead>
              <tbody>{resources.items.map((agency) => <tr key={agency.id} className="border-b border-border last:border-0">
                <td className="px-4 py-3 font-semibold">{agency.agency}<p className="mt-1 font-normal text-muted-foreground">{agency.description}</p></td><td className="px-4 py-3">{agency.category || "Uncategorized"}</td><td className="px-4 py-3">{agency.phone_number || "-"}</td><td className="px-4 py-3">{agency.address || "-"}</td>
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