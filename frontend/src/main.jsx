import React, { useState, useEffect, useCallback } from "react";
import { createRoot } from "react-dom/client";
import {
  LayoutDashboard,
  Inbox,
  Lightbulb,
  Smartphone,
  ShieldCheck,
  Settings,
  LogOut,
  ArrowUpRight,
  ArrowLeft,
  Search,
  Plus,
  ChevronRight,
  Check,
  Send,
  Wifi,
  WifiOff,
  RefreshCw,
  Download,
  MessageSquare,
  Clock,
  Bell,
  FileText,
  LockKeyhole,
  CheckCircle2,
  X,
  Users,
  ArrowRight,
  Leaf,
} from "lucide-react";
import { api, post, setAuth, getAuth } from "./api";
import {
  queued,
  enqueue,
  remove,
  clearQueue,
  requireEmptyQueue,
  sensitiveText,
  segments,
} from "./agent-pwa/queue";
import "./style.css";

const labels = {
  RECU: "Reçu",
  TRIE: "Trié",
  ATTRIBUE: "Attribué",
  EN_TRAITEMENT: "En traitement",
  REPONSE_PREPAREE: "Réponse préparée",
  REPONSE_TRANSMISE: "Réponse transmise",
  CLOTURE: "Clôturé",
  CLOISONNE: "Cloisonné",
  PRIS_EN_CHARGE: "Pris en charge",
  TRANSFERE: "Transféré",
  QUESTION: "Question",
  PLAINTE: "Plainte",
  SUGGESTION: "Suggestion",
  SATISFACTION: "Satisfaction",
  SMS_SIMULE: "SMS SIMULÉ",
  MESSAGERIE_SIMULEE: "MESSAGERIE SIMULÉE",
  WEB: "Web",
  AGENT: "Agent",
  PLANIFIEE: "Planifiée",
  EN_COURS: "En cours",
  REALISEE: "Réalisée",
  NORMALE: "Normale",
  URGENTE: "Urgente",
};
const roles = {
  R1: "Agent de collecte",
  R2: "Gestionnaire",
  R3: "Supervision MEAL",
  R4: "Référent sensible",
  R5: "Direction",
  R6: "Administration",
};
const fmt = (value) =>
  value
    ? new Date(value).toLocaleDateString("fr-FR", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "—";
const Badge = ({ value }) => (
  <span className={"badge " + value?.toLowerCase()}>
    {labels[value] || value}
  </span>
);
const Empty = ({ text = "Aucun résultat pour le moment." }) => (
  <div className="empty">
    <Inbox size={30} />
    <p>{text}</p>
  </div>
);
function Field({ label, children, ...props }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children || <input {...props} />}
    </label>
  );
}
function Select({ label, value, onChange, options, ...props }) {
  return (
    <Field label={label}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        {...props}
      >
        {options.map((v) => (
          <option
            key={typeof v === "string" ? v : v.value}
            value={typeof v === "string" ? v : v.value}
          >
            {typeof v === "string" ? labels[v] || v : v.label}
          </option>
        ))}
      </select>
    </Field>
  );
}
function Modal({ title, close, children }) {
  return (
    <div className="overlay" onClick={close}>
      <section
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="section-head">
          <h2>{title}</h2>
          <button className="icon-btn" aria-label="Fermer" onClick={close}>
            <X />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
function App() {
  const [user, setUser] = useState(getAuth()?.user || null),
    [page, setPage] = useState(location.hash.slice(1) || "login"),
    [config, setConfig] = useState(
      JSON.parse(localStorage.getItem("ecoute-public-config") || "null"),
    ),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [selected, setSelected] = useState(null),
    [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    api("/config")
      .then((value) => {
        setConfig(value);
        localStorage.setItem("ecoute-public-config", JSON.stringify(value));
      })
      .catch((e) => setError(e.message));
    const status = () => setOnline(navigator.onLine);
    const expire = () => {
      setUser(null);
      setPage("login");
      setError("Session expirée. Reconnectez-vous.");
    };
    window.addEventListener("online", status);
    window.addEventListener("offline", status);
    window.addEventListener("session-expired", expire);
    return () => {
      window.removeEventListener("online", status);
      window.removeEventListener("offline", status);
      window.removeEventListener("session-expired", expire);
    };
  }, []);
  const go = (value) => {
    setPage(value);
    setSelected(null);
    setError("");
    location.hash = value;
  };
  const execute = async (fn) => {
    setError("");
    try {
      return await fn();
    } catch (e) {
      setError(e.message);
      return null;
    }
  };
  const notify = (text) => {
    setNotice(text);
    setTimeout(() => setNotice(""), 4500);
  };
  const signout = async () => {
    const result = await execute(async () => {
      await requireEmptyQueue();
      await post("/auth/logout", {});
      return true;
    });
    if (result === null) return;
    await clearQueue();
    setAuth(null);
    setUser(null);
    go("login");
  };
  const common = { user, config, execute, notify, online };
  if (!config)
    return (
      <main className="loading">
        <Leaf />
        <h2>Écoute</h2>
        <p>{error || "Connexion à la plateforme…"}</p>
      </main>
    );
  const errorBox = error && (
    <div role="alert" className="alert error">
      <span>{error}</span>
      <button
        className="icon-btn"
        aria-label="Fermer l’erreur"
        onClick={() => setError("")}
      >
        <X size={17} />
      </button>
    </div>
  );
  if (page === "public")
    return (
      <>
        <PublicForm {...common} back={() => go(user ? "dashboard" : "login")} />
        {errorBox && <div className="floating-error">{errorBox}</div>}
      </>
    );
  if (!user)
    return (
      <div className="login-layout">
        <div className="login-story">
          <Brand />
          <div>
            <span className="eyebrow">CHAQUE VOIX COMPTE</span>
            <h1>
              Écouter.
              <br />
              Répondre.
              <br />
              <em>Agir ensemble.</em>
            </h1>
            <p>
              Un espace commun pour les retours des communautés et les actions
              qui en découlent.
            </p>
          </div>
          <small>Plateforme de feedback communautaire · Prototype OS3</small>
        </div>
        <div className="login-panel">
          <div className="login-form">
            <span className="eyebrow">ESPACE ÉQUIPE</span>
            <h2>Bienvenue sur Écoute</h2>
            <p className="muted">
              Connectez-vous pour retrouver votre espace de travail.
            </p>
            {errorBox}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = Object.fromEntries(new FormData(e.target));
                execute(async () => {
                  const auth = await post("/auth/login", f);
                  setAuth(auth);
                  setUser(auth.user);
                  go(
                    {
                      R1: "agent",
                      R2: "dossiers",
                      R4: "sensitive",
                      R6: "settings",
                    }[auth.user.role] || "dashboard",
                  );
                });
              }}
            >
              <Field
                label="Nom du compte"
                name="username"
                autoComplete="username"
                required
              />
              <Field
                label="Mot de passe"
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
              <Field
                label="Code d’authentification • référent et administrateur"
                name="otp"
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="6 chiffres, si requis"
              />
              <button className="primary wide">
                Se connecter <ArrowRight size={17} />
              </button>
            </form>
            <div className="login-footer">
              Vous souhaitez partager un retour ?
              <button className="text-button" onClick={() => go("public")}>
                Accéder au formulaire public <ArrowUpRight size={15} />
              </button>
            </div>
            <p className="demo-note">
              <ShieldCheck size={16} /> Démonstration sur données fictives.
              Comptes fournis dans le guide local.
            </p>
          </div>
        </div>
      </div>
    );
  if (page === "login") {
    const home =
      { R1: "agent", R2: "dossiers", R4: "sensitive", R6: "settings" }[
        user.role
      ] || "dashboard";
    go(home);
  }
  const nav = [
    ["dashboard", "Vue d’ensemble", LayoutDashboard, ["R3", "R5"]],
    ["dossiers", "Dossiers", Inbox, ["R1", "R2", "R3"]],
    ["actions", "Actions correctives", Lightbulb, ["R3", "R5"]],
    ["agent", "Collecte terrain", Smartphone, ["R1"]],
    ["sensitive", "Espace sensible", ShieldCheck, ["R4"]],
    ["simulator", "Simulateur multicanal", MessageSquare, ["R3"]],
    ["settings", "Paramètres", Settings, ["R3", "R6"]],
    ["audit", "Journal d’audit", FileText, ["R3", "R6"]],
  ].filter((n) => n[3].includes(user.role));
  return (
    <div className="app">
      <aside className="sidebar">
        <Brand />
        <div className="workspace">
          <span className="org-icon">AC</span>
          <div>
            Assistance communautaire<small>Espace de démonstration</small>
          </div>
        </div>
        <span className="nav-label">ESPACE DE TRAVAIL</span>
        <nav>
          {nav.map(([key, title, Icon]) => (
            <button
              key={key}
              className={page === key ? "active" : ""}
              onClick={() => go(key)}
            >
              <Icon size={19} />
              {title}
              {page === key && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="feedback-card">
            <Leaf size={22} />
            <strong>De l’écoute à l’action</strong>
            <p>Chaque retour est une occasion d’améliorer notre réponse.</p>
            <button onClick={() => go("public")}>
              Formulaire public <ArrowUpRight size={15} />
            </button>
          </div>
          <div className="profile">
            <div className="avatar">{user.first_name.slice(0, 1)}</div>
            <div>
              <strong>{user.first_name.split(" • ")[0]}</strong>
              <small>{roles[user.role]}</small>
            </div>
            <button
              className="icon-btn"
              aria-label="Se déconnecter"
              onClick={signout}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div className="breadcrumb">
            Espace de travail <ChevronRight size={14} />{" "}
            <strong>{nav.find((n) => n[0] === page)?.[1]}</strong>
          </div>
          <div className="topbar-right">
            <span className="demo-pill">DÉMONSTRATION</span>
            <span className="network">
              {online ? <Wifi size={15} /> : <WifiOff size={15} />}{" "}
              {online ? "En ligne" : "Hors ligne"}
            </span>
            <button
              className="icon-btn"
              aria-label="Notifications"
              onClick={() => go("notifications")}
            >
              <Bell size={19} />
            </button>
          </div>
        </header>
        <main className="content">
          {errorBox}
          {notice && (
            <div className="toast" role="status">
              <CheckCircle2 size={18} />
              {notice}
            </div>
          )}
          {selected ? (
            <CaseDetail
              {...common}
              id={selected}
              back={() => setSelected(null)}
            />
          ) : (
            <>
              {page === "dashboard" && (
                <Dashboard
                  {...common}
                  go={go}
                  select={(id) => {
                    setPage("dossiers");
                    setSelected(id);
                  }}
                />
              )}
              {page === "dossiers" && (
                <Dossiers {...common} select={setSelected} />
              )}
              {page === "actions" && <Actions {...common} />}
              {page === "simulator" && <Simulator {...common} />}
              {page === "agent" && <Agent {...common} />}
              {page === "sensitive" && <Sensitive {...common} />}
              {page === "settings" && <SettingsPage {...common} />}
              {page === "audit" && <AuditPage {...common} />}
              {page === "notifications" && <Notifications {...common} />}
            </>
          )}
        </main>
        <footer className="app-footer">
          Écoute · Plateforme de feedback communautaire
          <span>Données fictives · Prototype de recherche</span>
        </footer>
      </div>
    </div>
  );
}
function Brand() {
  return (
    <div className="brand">
      <span>
        <MessageSquare size={24} />
      </span>
      écoute<span className="brand-dot">.</span>
    </div>
  );
}
function ReturnFields({ config, sensitive, setSensitive }) {
  return (
    <>
      <Field label="Langue">
        <select name="language">
          {config.languages.map((l) => (
            <option value={l.code} key={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Quel type de retour souhaitez-vous partager ?">
        <select name="type">
          {["QUESTION", "PLAINTE", "SUGGESTION", "SATISFACTION"].map((v) => (
            <option value={v} key={v}>
              {labels[v]}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Votre message">
        <textarea
          name="text"
          required
          maxLength={8000}
          placeholder="Expliquez-nous votre question, votre difficulté ou votre idée…"
          disabled={sensitive}
        />
      </Field>
      <Field label="Zone">
        <select name="zone">
          {config.zones.map((z) => (
            <option key={z}>{z}</option>
          ))}
        </select>
      </Field>
      <Field label="Projet">
        <select name="project">
          {config.projects.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
      </Field>
      <Field
        label="Contact (facultatif)"
        name="address"
        placeholder="Téléphone ou autre moyen de contact"
        disabled={sensitive}
      />
      <label className="check">
        <input type="checkbox" name="consent" /> J’accepte d’être recontacté par
        ce moyen.
      </label>
      {setSensitive && (
        <label className="check sensitive-check">
          <input
            type="checkbox"
            checked={sensitive}
            onChange={(e) => {
              setSensitive(e.target.checked);
              if (e.target.checked) {
                e.target.form.elements.text.value = "";
                e.target.form.elements.address.value = "";
              }
            }}
          />{" "}
          Abus, exploitation, fraude ou danger
        </label>
      )}
    </>
  );
}
function PublicForm({ config, execute, back }) {
  const [receipt, setReceipt] = useState(null),
    [busy, setBusy] = useState(false),
    [key, setKey] = useState(crypto.randomUUID());
  return (
    <div className="public-page">
      <header>
        <Brand />
        <button className="text-button" onClick={back}>
          <ArrowLeft size={16} /> Espace équipe
        </button>
      </header>
      <main>
        <span className="eyebrow">NOUS SOMMES À VOTRE ÉCOUTE</span>
        <h1>
          Votre voix peut faire
          <br />
          la différence.
        </h1>
        <p>
          Une question, une difficulté, une idée ? Partagez votre retour en
          toute simplicité.
        </p>
        <section className="card">
          {receipt ? (
            <div className="receipt">
              <CheckCircle2 size={46} />
              <h2>Votre retour est bien reçu</h2>
              <p>Conservez cette référence.</p>
              <strong>{receipt.reference}</strong>
              <p>Échéance indicative : {fmt(receipt.due)}</p>
              <p className="muted">
                Sans contact, aucun rappel individuel n’est possible. Cette
                démonstration n’envoie aucun message réel.
              </p>
              <button
                className="secondary"
                onClick={() => {
                  setReceipt(null);
                  setKey(crypto.randomUUID());
                }}
              >
                Partager un autre retour
              </button>
            </div>
          ) : (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const f = Object.fromEntries(new FormData(e.target));
                setBusy(true);
                const r = await execute(() =>
                  post("/public/retours", {
                    ...f,
                    consent: f.consent === "on",
                    key,
                  }),
                );
                if (r) setReceipt(r);
                setBusy(false);
              }}
            >
              <div className="info">
                <ShieldCheck size={19} />
                <span>
                  Vous pouvez rester anonyme. Sans contact, nous ne pourrons pas
                  vous apporter de réponse individuelle.
                </span>
              </div>
              <ReturnFields config={config} />
              <button disabled={busy} className="primary wide">
                {busy ? "Envoi en cours…" : "Envoyer mon retour"}{" "}
                <Send size={16} />
              </button>
              <small className="muted">
                Prototype de démonstration : utilisez exclusivement des données
                fictives.
              </small>
            </form>
          )}
        </section>
      </main>
      <footer>Écoute · Un espace pour vous exprimer.</footer>
    </div>
  );
}
function Agent({ config, user, execute, notify, online }) {
  const [items, setItems] = useState([]),
    [sensitive, setSensitive] = useState(false),
    [busy, setBusy] = useState(false),
    [last, setLast] = useState("");
  const load = async () =>
    setItems((await queued()).filter((x) => x.agent === user.id));
  const sync = async () => {
    if (busy || !online) return;
    setBusy(true);
    await execute(async () => {
      const pending = (await queued()).filter((x) => x.agent === user.id);
      if (!pending.length) return;
      const r = await post("/agent/sync", { items: pending });
      let count = 0;
      for (const result of r.results) {
        if (result.reference) {
          await remove(result.key);
          count++;
        } else if (result.error?.includes("SENSIBLE")) {
          await remove(result.key);
          notify(
            "Saisie sensible retirée de l’appareil. Contactez le référent.",
          );
        }
      }
      setLast(new Date().toLocaleTimeString("fr-FR"));
      await load();
      notify(`${count} retour(s) synchronisé(s).`);
    });
    setBusy(false);
  };
  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    if (online) sync();
  }, [online]);
  return (
    <>
      <PageHead
        eyebrow="APPLICATION AGENT"
        title="Collecte terrain"
        description="Saisir pour un usager, même lorsque la connexion est instable."
      />
      <div className="agent-grid">
        <section className="card padded">
          <h2>Nouveau retour ordinaire</h2>
          <p className="muted">Saisi par {user.first_name} pour un usager.</p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (sensitive) return;
              const form = e.target;
              const f = Object.fromEntries(new FormData(form));
              if (sensitiveText(f.text, config.keywords)) {
                form.reset();
                setSensitive(true);
                return;
              }
              await enqueue({
                ...f,
                consent: f.consent === "on",
                key: crypto.randomUUID(),
                agent: user.id,
              });
              form.reset();
              await load();
              notify("Retour conservé dans la file locale.");
              if (online) sync();
            }}
          >
            <ReturnFields
              config={config}
              sensitive={sensitive}
              setSensitive={setSensitive}
            />
            {sensitive ? (
              <div className="alert">
                <ShieldCheck />
                <div>
                  <strong>Aucun contenu sensible n’est enregistré.</strong>
                  <p>{config.referral_contact}</p>
                </div>
              </div>
            ) : (
              <button className="primary wide">
                {online
                  ? "Enregistrer et synchroniser"
                  : "Enregistrer dans la file locale"}
              </button>
            )}
          </form>
        </section>
        <section className="card padded">
          <div className="section-head">
            <h2>File d’envoi</h2>
            <span className="badge neutral">{items.length} en attente</span>
          </div>
          <p className="muted">
            {online
              ? "Connexion disponible"
              : "Hors ligne : les retours restent sur cet appareil."}
          </p>
          {items.length ? (
            items.map((i) => (
              <div className="queue-item" key={i.key}>
                <div>
                  <strong>
                    {labels[i.type]} · {i.zone}
                  </strong>
                  <p>{i.text}</p>
                </div>
                <button
                  className="icon-btn"
                  aria-label="Supprimer la saisie locale"
                  onClick={async () => {
                    await remove(i.key);
                    load();
                  }}
                >
                  <X size={16} />
                </button>
              </div>
            ))
          ) : (
            <Empty text="Tous les retours ont été transmis." />
          )}
          <button
            disabled={!online || busy}
            className="secondary wide"
            onClick={sync}
          >
            <RefreshCw size={16} />
            {busy ? "Synchronisation…" : "Envoyer maintenant"}
          </button>
          <small className="muted">
            Dernière synchronisation : {last || "Aucune dans cette session"}. La
            déconnexion est bloquée tant que des retours restent en attente.
          </small>
        </section>
      </div>
    </>
  );
}
function Simulator({ execute, notify }) {
  const [channel, setChannel] = useState("sms"),
    [text, setText] = useState(""),
    [address, setAddress] = useState("TEST-VISITEUR-001"),
    [messages, setMessages] = useState([]),
    [result, setResult] = useState(null),
    [busy, setBusy] = useState(false),
    [key, setKey] = useState(crypto.randomUUID());
  const load = () => execute(async () => setMessages(await api("/simulator")));
  useEffect(() => {
    load();
  }, []);
  const send = async (replay = false) => {
    setBusy(true);
    await execute(async () => {
      const response = await post("/simulator", {
        channel,
        text,
        address,
        consent: true,
        key,
      });
      setResult(response);
      if (!replay) notify("Message reçu par le traitement signé.");
      await load();
    });
    setBusy(false);
  };
  return (
    <>
      <PageHead
        eyebrow="LABORATOIRE MULTICANAL"
        title="Console de simulation"
        description="Tester les échanges par le même traitement signé que les webhooks."
      />
      <div className="simulation-banner">
        <Smartphone size={20} />
        <strong>SIMULATION</strong> Aucun message réel envoyé. Utilisez
        uniquement des contenus et identifiants fictifs.
      </div>
      <div className="sim-grid">
        <section className="phone">
          <div className="phone-top">
            <span /> Écoute · SIMULÉ <span />
          </div>
          <div className="phone-body">
            <Select
              label="Canal"
              value={channel}
              onChange={setChannel}
              options={[
                { value: "sms", label: "SMS SIMULÉ" },
                { value: "messagerie", label: "MESSAGERIE SIMULÉE" },
              ]}
            />
            <Field
              label="Identifiant fictif de l’expéditeur"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
            />
            <div className="phone-thread">
              <p className="sms-bubble incoming">
                Bonjour ! Écrivez votre retour pour tester la réception.
              </p>
              {result && (
                <p className="sms-bubble incoming">
                  {result.message}
                  <br />
                  <strong>{result.reference}</strong>
                  {result.duplicate && (
                    <small>Rejeu reconnu : aucun doublon créé.</small>
                  )}
                </p>
              )}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send();
              }}
            >
              <Field label="Message de test">
                <textarea
                  required
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value);
                    setKey(crypto.randomUUID());
                  }}
                  placeholder="Ex. Les kits ne sont pas encore arrivés."
                />
              </Field>
              <div className="sms-counter">
                {segments(text).length} caractères · {segments(text).count}{" "}
                segment(s) · {segments(text).unicode ? "Unicode" : "GSM-7"}
              </div>
              <button
                disabled={busy || !address.trim()}
                className="primary wide"
              >
                <Send size={16} /> Envoyer le message simulé
              </button>
            </form>
            {result && (
              <button className="text-button" onClick={() => send(true)}>
                Rejouer le même message (idempotence)
              </button>
            )}
          </div>
        </section>
        <section className="card">
          <div className="section-head">
            <div>
              <h2>Boîte d’envoi simulée</h2>
              <p>Accusés de réception et réponses validées.</p>
            </div>
            <button className="icon-btn" aria-label="Actualiser" onClick={load}>
              <RefreshCw size={18} />
            </button>
          </div>
          <div className="outbox">
            {messages.map((m) => (
              <article className="message" key={m.id}>
                <header>
                  <strong>{m.dossier__reference}</strong>
                  <Badge value={m.status} />
                </header>
                <p>{m.text}</p>
                <small>
                  {labels[m.channel]} · {fmt(m.created)} · {m.attempts}{" "}
                  tentative(s)
                </small>
              </article>
            ))}
            {!messages.length && (
              <Empty text="Les messages sortants apparaîtront ici." />
            )}
          </div>
        </section>
      </div>
    </>
  );
}
function Actions({ config, execute, notify }) {
  const [items, setItems] = useState([]),
    [users, setUsers] = useState([]),
    [cases, setCases] = useState([]),
    [modal, setModal] = useState(null);
  const load = () =>
    execute(async () => {
      setItems(await api("/actions"));
      setUsers(await api("/admin/users"));
      let r = await api("/dossiers");
      let all = r.results;
      while (r.next) {
        r = await api("/dossiers?cursor=" + encodeURIComponent(r.next));
        all.push(...r.results);
      }
      setCases(all);
    });
  useEffect(() => {
    load();
  }, []);
  return (
    <>
      <PageHead
        eyebrow="APPRENTISSAGE & RESTITUTION"
        title="Actions correctives"
        description="Transformer les retours en améliorations concrètes pour les communautés."
      >
        <button className="primary" onClick={() => setModal({ kind: "new" })}>
          <Plus size={16} /> Créer une action
        </button>
      </PageHead>
      <div className="action-grid">
        {items.map((a) => (
          <section className="card action-card" key={a.id}>
            <div className="section-head">
              <span className="action-symbol">
                <Lightbulb size={21} />
              </span>
              <Badge value={a.status} />
            </div>
            <h2>{a.title}</h2>
            <p className="muted">{a.project}</p>
            <div className="action-meta">
              <span>
                <Users size={15} />
                {a.owner_name}
              </span>
              <span>
                <Clock size={15} />
                {fmt(a.due)}
              </span>
            </div>
            <div className="action-count">
              {a.dossiers.length} dossiers liés · {a.restitutions.length}{" "}
              restitutions
            </div>
            {a.proof && <p>Preuve : {a.proof}</p>}
            {a.status === "REALISEE" && !a.restitutions.length && (
              <div className="alert">Restitution à la communauté attendue.</div>
            )}
            {a.restitutions.map((r) => (
              <div className="restitution" key={r.id}>
                <CheckCircle2 size={16} />
                <div>
                  <strong>
                    {r.channel} · {r.zone}
                  </strong>
                  <p>{r.message}</p>
                  <small>{fmt(r.date)}</small>
                </div>
              </div>
            ))}
            <div className="button-row">
              <button
                className="secondary"
                onClick={() => setModal({ kind: "edit", action: a })}
              >
                Mettre à jour
              </button>
              <button
                className="text-button"
                onClick={() => setModal({ kind: "restitution", action: a })}
              >
                Restituer <ArrowRight size={14} />
              </button>
            </div>
          </section>
        ))}
      </div>
      {!items.length && <Empty text="Créez une première action corrective." />}
      {modal && (
        <Modal
          title={
            modal.kind === "restitution"
              ? "Enregistrer la restitution"
              : modal.kind === "new"
                ? "Nouvelle action corrective"
                : "Mettre à jour l’action"
          }
          close={() => setModal(null)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const fd = new FormData(e.target),
                f = Object.fromEntries(fd);
              execute(async () => {
                if (modal.kind === "restitution")
                  await post(`/actions/${modal.action.id}/restitutions`, f);
                else {
                  f.owner = Number(f.owner);
                  f.dossiers = fd.getAll("dossiers");
                  await api(
                    "/actions" + (modal.action ? "/" + modal.action.id : ""),
                    { method: modal.action ? "PATCH" : "POST", body: f },
                  );
                }
                setModal(null);
                await load();
                notify("Action enregistrée.");
              });
            }}
          >
            {modal.kind === "restitution" ? (
              <>
                <Field label="Date" name="date" type="date" required />
                <Field
                  label="Canal de restitution"
                  name="channel"
                  placeholder="Réunion communautaire, affichage…"
                  required
                />
                <Field label="Zone" name="zone" required />
                <Field label="Message partagé">
                  <textarea name="message" required />
                </Field>
              </>
            ) : (
              <>
                <Field
                  label="Intitulé"
                  name="title"
                  defaultValue={modal.action?.title}
                  required
                />
                <Field label="Projet">
                  <select name="project" defaultValue={modal.action?.project}>
                    {config.projects.map((p) => (
                      <option key={p}>{p}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Responsable">
                  <select name="owner" defaultValue={modal.action?.owner}>
                    {users.map((u) => (
                      <option value={u.id} key={u.id}>
                        {u.first_name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label="Échéance"
                  name="due"
                  type="date"
                  defaultValue={modal.action?.due}
                  required
                />
                <Field label="Statut">
                  <select name="status" defaultValue={modal.action?.status}>
                    {["PLANIFIEE", "EN_COURS", "REALISEE"].map((s) => (
                      <option value={s} key={s}>
                        {labels[s]}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Preuve de mise en œuvre">
                  <textarea name="proof" defaultValue={modal.action?.proof} />
                </Field>
                <Field label="Dossiers liés (sélection multiple)">
                  <select
                    name="dossiers"
                    multiple
                    defaultValue={modal.action?.dossiers || []}
                  >
                    {cases.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.reference} · {d.zone}
                      </option>
                    ))}
                  </select>
                </Field>
              </>
            )}
            <button className="primary wide">Enregistrer</button>
          </form>
        </Modal>
      )}
    </>
  );
}
function Sensitive({ execute, notify }) {
  const [items, setItems] = useState([]),
    [d, setD] = useState(null);
  const load = () => execute(async () => setItems(await api("/sensible")));
  useEffect(() => {
    load();
  }, []);
  const open = (id) => execute(async () => setD(await api("/sensible/" + id)));
  return (
    <>
      <PageHead
        eyebrow="ACCÈS RÉSERVÉ AU RÉFÉRENT"
        title="Espace sensible"
        description="Prendre en charge et orienter vers le circuit spécialisé."
      />
      <div className="confidential-banner">
        <LockKeyhole size={20} />
        <strong>Confidentiel</strong> Chaque consultation est journalisée. La
        plateforme ne conduit aucune enquête.
      </div>
      {d ? (
        <section className="card padded">
          <button className="text-button" onClick={() => setD(null)}>
            <ArrowLeft size={15} /> Retour à la liste
          </button>
          <div className="section-head">
            <h2>{d.reference}</h2>
            <Badge value={d.state} />
          </div>
          {d.messages.map((m) => (
            <article className="message" key={m.id}>
              <p>{m.text}</p>
              <small>{fmt(m.created)}</small>
            </article>
          ))}
          {d.transfer.recipient && (
            <p>
              Transfert : {d.transfer.recipient} · {fmt(d.transfer.date)}
            </p>
          )}
          {d.transfer.receipt && (
            <p>Accusé de prise en charge : {d.transfer.receipt}</p>
          )}
          {d.state !== "CLOTURE" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = Object.fromEntries(new FormData(e.target));
                execute(async () => {
                  setD(
                    await post("/sensible/" + d.id, {
                      ...f,
                      state: {
                        CLOISONNE: "PRIS_EN_CHARGE",
                        PRIS_EN_CHARGE: "TRANSFERE",
                        TRANSFERE: "CLOTURE",
                      }[d.state],
                    }),
                  );
                  load();
                  notify("Étape enregistrée dans le circuit sensible.");
                });
              }}
            >
              {d.state === "PRIS_EN_CHARGE" && (
                <Field
                  label="Circuit spécialisé destinataire"
                  name="recipient"
                  required
                />
              )}
              {d.state === "TRANSFERE" && (
                <Field
                  label="Accusé de prise en charge reçu"
                  name="receipt"
                  required
                />
              )}
              <button className="primary">
                {d.state === "CLOISONNE"
                  ? "Prendre en charge"
                  : d.state === "PRIS_EN_CHARGE"
                    ? "Enregistrer le transfert"
                    : "Clôturer après accusé"}
              </button>
            </form>
          )}
        </section>
      ) : (
        <section className="card">
          <CaseTable rows={items} select={open} />
        </section>
      )}
    </>
  );
}
function SettingsPage({ user, execute, notify }) {
  const [value, setValue] = useState(""),
    [users, setUsers] = useState([]),
    [tab, setTab] = useState("settings"),
    [enrollment, setEnrollment] = useState(null);
  const load = () =>
    execute(async () => {
      setValue(JSON.stringify(await api("/admin/settings"), null, 2));
      if (user.role === "R6") setUsers(await api("/admin/users"));
    });
  useEffect(() => {
    load();
  }, []);
  return (
    <>
      <PageHead
        eyebrow="ADMINISTRATION"
        title="Paramètres de la plateforme"
        description="Adapter les référentiels, les délais et les modèles sans redéploiement."
      />
      <div className="tabs">
        <button onClick={() => setTab("settings")}>Référentiels métier</button>
        {user.role === "R6" && (
          <button onClick={() => setTab("users")}>Comptes et rôles</button>
        )}
      </div>
      {tab === "settings" ? (
        <section className="card padded">
          <h2>Configuration métier</h2>
          <p className="muted">
            Éditeur JSON du prototype. Les délais sont en jours ouvrés. Les
            langues locales doivent être validées avec l’ONG avant leur
            activation.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              execute(async () => {
                await api("/admin/settings", {
                  method: "PATCH",
                  body: JSON.parse(value),
                });
                notify(
                  "Paramètres enregistrés. Rechargez la page pour les appliquer aux formulaires.",
                );
              });
            }}
          >
            <Field label="Référentiels">
              <textarea
                className="json-editor"
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </Field>
            <button className="primary">Enregistrer la configuration</button>
          </form>
        </section>
      ) : (
        <section className="card padded">
          <h2>Comptes de l’équipe</h2>
          {users.map((u) => (
            <div className="user-row" key={u.id}>
              <div>
                <strong>{u.first_name}</strong>
                <small>
                  {u.username} · {roles[u.role]}
                </small>
              </div>
              <Badge value={u.is_active ? "Actif" : "Inactif"} />
              {u.id !== user.id && (
                <button
                  className="secondary"
                  onClick={() =>
                    execute(async () => {
                      await api("/admin/users/" + u.id, {
                        method: "PATCH",
                        body: { is_active: !u.is_active },
                      });
                      load();
                    })
                  }
                >
                  {u.is_active ? "Désactiver" : "Réactiver"}
                </button>
              )}
            </div>
          ))}
          <h3>Créer un compte</h3>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = Object.fromEntries(new FormData(e.target));
              execute(async () => {
                const r = await post("/admin/users", f);
                setEnrollment(r.totp_enrollment);
                load();
                notify("Compte créé.");
              });
            }}
          >
            <div className="two-cols">
              <Field label="Nom du compte" name="username" required />
              <Field label="Nom affiché" name="first_name" required />
              <Field
                label="Mot de passe initial"
                type="password"
                name="password"
                minLength={10}
                required
              />
              <Field label="Rôle">
                <select name="role">
                  {Object.entries(roles).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <button className="primary">Créer le compte</button>
          </form>
          {enrollment && (
            <div className="alert">
              Secret d’enrôlement TOTP à transmettre par un canal sûr :{" "}
              <code>{enrollment}</code>
            </div>
          )}
        </section>
      )}
    </>
  );
}
function AuditPage({ execute }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    execute(async () => setData(await api("/audit")));
  }, []);
  return (
    <>
      <PageHead
        eyebrow="TRAÇABILITÉ"
        title="Journal d’audit"
        description="Un journal chaîné, consultable en lecture seule."
      />
      {data && (
        <section className="card padded">
          <div className="info">
            <ShieldCheck size={20} />
            {data.valid
              ? "Chaîne d’intégrité vérifiée"
              : "Anomalie dans la chaîne d’intégrité"}
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>DATE</th>
                  <th>ACTION</th>
                  <th>AUTEUR</th>
                  <th>OBJET</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((r) => (
                  <tr key={r.id}>
                    <td>{fmt(r.created)}</td>
                    <td>{r.action}</td>
                    <td>{r.actor_id || "Système"}</td>
                    <td>
                      <code>{r.object_id}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
function Notifications({ execute }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    execute(async () => setItems(await api("/notifications")));
  }, []);
  return (
    <>
      <PageHead
        eyebrow="SUIVI"
        title="Notifications"
        description="Alertes de votre équipe, sans contenu ni coordonnées personnelles."
      />
      <section className="card padded">
        {items.map((n) => (
          <div className="timeline" key={n.id}>
            <Bell size={17} />
            <div>
              <strong>{n.event__event}</strong>
              <p>Objet : {n.event__object_id}</p>
              <small>{fmt(n.event__created)}</small>
            </div>
          </div>
        ))}
        {!items.length && <Empty />}
      </section>
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);
if ("serviceWorker" in navigator && import.meta.env.PROD)
  navigator.serviceWorker.register("/sw.js");
function PageHead({ eyebrow, title, description, children }) {
  return (
    <div className="page-head">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="head-actions">{children}</div>
    </div>
  );
}
function Deadline({ d }) {
  if (d.state === "CLOTURE")
    return (
      <span className="deadline done">
        <Check size={13} /> Clôturé
      </span>
    );
  const days = Math.ceil((new Date(d.due) - new Date()) / 86400000);
  return (
    <span
      className={"deadline " + (days < 0 ? "late" : days <= 1 ? "soon" : "")}
    >
      <span />
      {days < 0
        ? `${Math.abs(days)} j de retard`
        : days === 0
          ? "Aujourd’hui"
          : `Dans ${days} jours`}
    </span>
  );
}
function CaseTable({ rows, select }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>DOSSIER / RETOUR</th>
            <th>CANAL</th>
            <th>STATUT</th>
            <th>RESPONSABLE</th>
            <th>ÉCHÉANCE</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => (
            <tr key={d.id} onClick={() => select(d.id)}>
              <td>
                <button
                  className="row-link"
                  onClick={(e) => {
                    e.stopPropagation();
                    select(d.id);
                  }}
                >
                  {d.reference}
                </button>
                <span className="table-preview">{d.preview}</span>
                <small>
                  {d.zone} · {labels[d.type]}
                </small>
              </td>
              <td>
                <span className="channel">
                  <MessageSquare size={14} />
                  {labels[d.channel]}
                </span>
              </td>
              <td>
                <Badge value={d.state} />
              </td>
              <td>
                {d.owner_name ? (
                  <span className="person">
                    <span>{d.owner_name[0]}</span>
                    {d.owner_name.split(" • ")[0]}
                  </span>
                ) : (
                  <span className="muted">Non attribué</span>
                )}
              </td>
              <td>
                <Deadline d={d} />
                <small>{fmt(d.due)}</small>
              </td>
              <td>
                <ChevronRight size={16} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <Empty />}
    </div>
  );
}
function Dashboard({ config, execute, go, select, user }) {
  const [data, setData] = useState(null),
    [rows, setRows] = useState([]),
    [project, setProject] = useState(""),
    [from, setFrom] = useState(""),
    [to, setTo] = useState("");
  const query = new URLSearchParams({ project, from, to }).toString();
  useEffect(() => {
    execute(async () => {
      setData(await api("/indicateurs?" + query));
      if (user.role === "R3")
        setRows((await api("/dossiers")).results.slice(0, 5));
    });
  }, [query]);
  const download = async (format) =>
    execute(async () => {
      const blob = await api("/exports", {
        method: "POST",
        body: { format, project, from, to },
        blob: true,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "feedback-export." + format;
      a.click();
      URL.revokeObjectURL(url);
    });
  if (!data) return <Empty text="Chargement des indicateurs…" />;
  const channels = data.counts.channel,
    total = Math.max(data.total, 1),
    colors = ["#23695b", "#81ad97", "#d6ad58", "#aac6db"];
  let offset = 0;
  const stops = Object.values(channels)
    .map((n, i) => {
      const start = offset;
      offset += (n / total) * 100;
      return `${colors[i % colors.length]} ${start}% ${offset}%`;
    })
    .join(",");
  return (
    <>
      <PageHead
        eyebrow="PILOTAGE & REDEVABILITÉ"
        title="Vue d’ensemble"
        description="Les voix de vos communautés, les progrès de votre équipe."
      >
        <button className="secondary" onClick={() => download("csv")}>
          <Download size={16} /> Exporter CSV
        </button>
        <button className="primary" onClick={() => go("public")}>
          <Plus size={17} /> Nouveau retour
        </button>
      </PageHead>
      <div className="filter-bar">
        <div>
          <Select
            label="Projet"
            value={project}
            onChange={setProject}
            options={[
              { value: "", label: "Tous les projets" },
              ...config.projects,
            ]}
          />
          <Field
            label="Du"
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
          <Field
            label="Au"
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
        <span>
          <span className="live-dot" /> Données actualisées
        </span>
      </div>
      <div className="stats-grid">
        {[
          [Inbox, "Retours reçus", data.total, "Dossiers ordinaires", ""],
          [
            MessageSquare,
            "Dossiers en cours",
            data.open,
            "À suivre par l’équipe",
            "",
          ],
          [
            Clock,
            "Échéances dépassées",
            data.late,
            "Nécessitent votre attention",
            "warning",
          ],
          [
            CheckCircle2,
            "Dossiers clôturés",
            data.closed,
            `${data.indicators.I03 ?? "—"} % de réponse de fond`,
            "",
          ],
        ].map(([Icon, label, value, sub, cls]) => (
          <div key={label} className={"stat-card " + cls}>
            <div>
              <span>{label}</span>
              <Icon size={19} />
            </div>
            <strong>{value}</strong>
            <small>
              {cls && <span className="live-dot amber" />}
              {sub}
            </small>
          </div>
        ))}
      </div>
      <div className="dashboard-grid">
        <section className="card journey">
          <div className="section-head">
            <div>
              <h2>De l’écoute au changement</h2>
              <p>Suivre les étapes qui donnent du sens aux retours.</p>
            </div>
            <span className="badge neutral">CIRCUIT ORDINAIRE</span>
          </div>
          <div className="journey-steps">
            {[
              ["Retours reçus", data.total, Inbox],
              [
                "Réponse de fond",
                data.indicators.I03 === null ? "—" : data.indicators.I03 + " %",
                MessageSquare,
              ],
              [
                "Liés à une action",
                data.indicators.I06 === null ? "—" : data.indicators.I06 + " %",
                Lightbulb,
              ],
              [
                "Restitution",
                data.indicators.I07 === null ? "—" : data.indicators.I07 + " %",
                Users,
              ],
            ].map(([label, value, Icon], i) => (
              <React.Fragment key={label}>
                {i > 0 && <ArrowRight className="step-arrow" size={16} />}
                <div className="journey-step">
                  <span>
                    <Icon size={20} />
                  </span>
                  <strong>{value}</strong>
                  <small>{label}</small>
                </div>
              </React.Fragment>
            ))}
          </div>
          <div className="insight">
            <Lightbulb size={18} />
            <span>
              {data.actions_without_restitution
                ? `${data.actions_without_restitution} action(s) réalisée(s) attendent une restitution à la communauté.`
                : "Reliez les dossiers aux actions pour rendre les améliorations visibles."}
            </span>
            <button className="text-button" onClick={() => go("actions")}>
              Voir les actions <ArrowRight size={14} />
            </button>
          </div>
        </section>
        <section className="card channels-card">
          <div className="section-head">
            <div>
              <h2>Canaux d’écoute</h2>
              <p>D’où viennent les retours ?</p>
            </div>
          </div>
          <div className="channel-chart">
            <div
              className="donut"
              style={{
                background: stops ? `conic-gradient(${stops})` : "#e8eee9",
              }}
            >
              <div>
                <strong>{data.total}</strong>
                <small>retours</small>
              </div>
            </div>
            <div className="legend">
              {Object.entries(channels).map(([channel, n], i) => (
                <div key={channel}>
                  <span style={{ background: colors[i % colors.length] }} />
                  <small>{labels[channel]}</small>
                  <strong>{n}</strong>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
      {user.role === "R3" && (
        <section className="card recent">
          <div className="section-head">
            <div>
              <h2>Derniers dossiers</h2>
              <p>Les retours récemment reçus par votre équipe.</p>
            </div>
            <button className="text-button" onClick={() => go("dossiers")}>
              Tous les dossiers <ArrowRight size={15} />
            </button>
          </div>
          <CaseTable rows={rows} select={select} />
        </section>
      )}
      <div className="bottom-grid">
        <section className="card compact">
          <ShieldCheck size={24} />
          <div>
            <h3>Un circuit sensible protégé</h3>
            <p>
              {data.sensitive_total} signalements cloisonnés. Seuls les
              référents habilités accèdent à leur contenu.
            </p>
          </div>
          <LockKeyhole size={18} />
        </section>
        <section className="card compact">
          <Clock size={24} />
          <div>
            <h3>{data.indicators.I02 ?? "—"} jours ouvrés</h3>
            <p>Délai médian de réponse de fond · I02</p>
          </div>
        </section>
      </div>
      <details className="card indicators">
        <summary>Consulter les dix indicateurs de redevabilité</summary>
        <div className="metric-list">
          {Object.entries(data.indicators).map(([key, value]) => (
            <div key={key}>
              <strong>{key}</strong>
              <span>
                {typeof value === "object" && value !== null
                  ? JSON.stringify(value)
                  : `${value ?? "Non calculable"}${key === "I02" ? " jours" : value !== null ? " %" : ""}`}
              </span>
            </div>
          ))}
        </div>
        <button className="secondary" onClick={() => download("xlsx")}>
          <Download size={15} /> Exporter XLSX
        </button>
        <p className="muted">
          {data.anonymous} dossiers sans contact, exclus du taux de réponse de
          fond. « — » signifie que le dénominateur est nul.
        </p>
      </details>
    </>
  );
}
function Dossiers({ execute, select }) {
  const [rows, setRows] = useState([]),
    [q, setQ] = useState(""),
    [state, setState] = useState(""),
    [late, setLate] = useState(false),
    [next, setNext] = useState(null),
    [count, setCount] = useState(0);
  const load = useCallback(
    (cursor) =>
      execute(async () => {
        const r = await api(
          "/dossiers?" +
            new URLSearchParams({
              q,
              state,
              late: late ? "1" : "",
              ...(cursor ? { cursor } : {}),
            }),
        );
        setRows((prev) => (cursor ? [...prev, ...r.results] : r.results));
        setNext(r.next);
        setCount(r.count);
      }),
    [q, state, late],
  );
  useEffect(() => {
    const timer = setTimeout(() => load(), 250);
    return () => clearTimeout(timer);
  }, [load]);
  return (
    <>
      <PageHead
        eyebrow="RÉCEPTION & TRAITEMENT"
        title="Les dossiers"
        description="Qualifier chaque retour, attribuer une réponse, garder le fil."
      />
      <section className="card">
        <div className="list-controls">
          <div className="search">
            <Search size={18} />
            <input
              aria-label="Rechercher un dossier"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Rechercher une référence, un message…"
            />
          </div>
          <Select
            label="Statut"
            value={state}
            onChange={setState}
            options={[
              { value: "", label: "Tous les statuts" },
              ...[
                "RECU",
                "TRIE",
                "ATTRIBUE",
                "EN_TRAITEMENT",
                "REPONSE_PREPAREE",
                "REPONSE_TRANSMISE",
                "CLOTURE",
              ],
            ]}
          />
          <label className="check">
            <input
              type="checkbox"
              checked={late}
              onChange={(e) => setLate(e.target.checked)}
            />{" "}
            En retard
          </label>
          <span className="muted">{count} dossiers</span>
        </div>
        <CaseTable rows={rows} select={select} />
        {next && (
          <button className="secondary load-more" onClick={() => load(next)}>
            Afficher la suite
          </button>
        )}
      </section>
    </>
  );
}
function CaseDetail({ id, user, config, execute, notify, back }) {
  const [d, setD] = useState(null),
    [users, setUsers] = useState([]),
    [tab, setTab] = useState("messages"),
    [modal, setModal] = useState(null),
    [text, setText] = useState("");
  const load = () =>
    execute(async () => {
      setD(await api("/dossiers/" + id));
      if (user.role === "R3") setUsers(await api("/admin/users"));
    });
  useEffect(() => {
    load();
  }, [id]);
  const change = async (path, body, method = "POST") =>
    execute(async () => {
      await api("/dossiers/" + id + path, { method, body });
      setModal(null);
      setText("");
      notify("Modification enregistrée.");
      if (body.sensitive) {
        back();
        return;
      }
      await load();
    });
  if (!d) return <Empty text="Chargement du dossier…" />;
  const canWork = ["R2", "R3"].includes(user.role),
    supervisor = user.role === "R3";
  return (
    <>
      <button className="back text-button" onClick={back}>
        <ArrowLeft size={16} /> Retour aux dossiers
      </button>
      <PageHead
        eyebrow={`${labels[d.channel]} · ${fmt(d.created)}`}
        title={d.reference}
        description={`${labels[d.type]} · ${d.zone} · ${d.project}`}
      >
        <Badge value={d.state} />
        {supervisor && (
          <button
            className="secondary"
            onClick={() => setModal("qualification")}
          >
            Qualifier le dossier
          </button>
        )}
      </PageHead>
      {d.reopen_requested && (
        <div className="alert">
          Un nouveau message demande l’examen d’une réouverture.
        </div>
      )}
      <div className="case-grid">
        <section className="card">
          <div className="tabs">
            {[
              ["messages", "Messages"],
              ["history", "Historique"],
              ["reply", "Réponse & suivi"],
              ["actions", "Actions liées"],
            ].map(([key, label]) => (
              <button
                className={tab === key ? "active" : ""}
                onClick={() => setTab(key)}
                key={key}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="case-body">
            {tab === "messages" && (
              <>
                {d.agent_name && (
                  <p className="info">
                    Saisi par {d.agent_name} pour un usager.
                  </p>
                )}
                {d.messages.map((m) => (
                  <article className="message" key={m.id}>
                    <header>
                      <span>
                        <MessageSquare size={16} /> Message reçu ·{" "}
                        {labels[m.channel]}
                      </span>
                      <small>{fmt(m.created)}</small>
                    </header>
                    <p>{m.text}</p>
                  </article>
                ))}
                {d.records
                  .filter((r) =>
                    ["NOTE", "TENTATIVE", "REFERENCEMENT"].includes(r.kind),
                  )
                  .map((r) => (
                    <article className="message internal" key={r.id}>
                      <header>
                        {r.kind} · {r.author__first_name}
                      </header>
                      <p>
                        {r.data.text || `${r.data.recipient} — ${r.data.issue}`}
                      </p>
                      {r.kind === "REFERENCEMENT" && canWork && (
                        <button
                          className="text-button"
                          onClick={() =>
                            setModal({ kind: "referral", record: r })
                          }
                        >
                          Mettre à jour l’issue
                        </button>
                      )}
                    </article>
                  ))}
                {canWork && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      change("/notes", {
                        text,
                        attempt: e.target.attempt.checked,
                      });
                    }}
                  >
                    <Field label="Ajouter une note interne">
                      <textarea
                        required
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        placeholder="Cette note reste interne à l’équipe."
                      />
                    </Field>
                    <label className="check">
                      <input type="checkbox" name="attempt" /> Documenter une
                      tentative de contact
                    </label>
                    <button className="primary">Enregistrer la note</button>
                  </form>
                )}
              </>
            )}
            {tab === "history" &&
              d.records.map((r) => (
                <div className="timeline" key={r.id}>
                  <span />
                  <div>
                    <strong>{r.kind.replaceAll("_", " ")}</strong>
                    <small>
                      {fmt(r.created)} · {r.author__first_name}
                    </small>
                    <p>{JSON.stringify(r.data)}</p>
                  </div>
                </div>
              ))}
            {tab === "reply" && (
              <>
                <div className="info">
                  Canal de rappel : {labels[d.contact.channel] || "Aucun"} ·{" "}
                  {d.contact.stopped
                    ? "STOP reçu"
                    : d.contact.consent
                      ? "Consentement enregistré"
                      : "Pas de consentement"}
                </div>
                {d.replies.map((r) => (
                  <article className="message" key={r.id}>
                    <header>
                      <Badge value={r.status} />
                      <small>{fmt(r.created)}</small>
                    </header>
                    <p>{r.text}</p>
                    <small>
                      {segments(r.text).count} segment(s) SMS ·{" "}
                      {segments(r.text).unicode ? "Unicode" : "GSM-7"}
                    </small>
                    {supervisor && r.status === "PREPAREE" && (
                      <div className="button-row">
                        <button
                          className="primary"
                          onClick={() =>
                            ['WEB','AGENT'].includes(d.contact.channel) ? setModal({kind:'manual',reply:r.id}) : change(`/reponses/${r.id}/validation`, {
                              accepted: true,
                            })
                          }
                        >
                          <Send size={15} /> {['WEB','AGENT'].includes(d.contact.channel)?'Documenter la transmission':'Valider et envoyer'}
                        </button>
                        <button
                          className="secondary"
                          onClick={() =>
                            setModal({ kind: "reject", reply: r.id })
                          }
                        >
                          Refuser
                        </button>
                      </div>
                    )}
                    {canWork &&
                      ["TRANSMISE", "RECUE"].includes(r.status) &&
                      !r.understood && (
                        <button
                          className="text-button"
                          onClick={() =>
                            change(`/reponses/${r.id}/comprehension`, {})
                          }
                        >
                          Confirmer la compréhension
                        </button>
                      )}
                    {r.understood && (
                      <p className="muted">
                        Compréhension confirmée le {fmt(r.understood)}
                      </p>
                    )}
                  </article>
                ))}
                {canWork && d.state === "EN_TRAITEMENT" && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      change("/reponses", { text });
                    }}
                  >
                    <Field label="Rédiger une réponse de fond">
                      <textarea
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        required
                        placeholder="Réponse à l’usager, à valider par la supervision."
                      />
                    </Field>
                    <small className="muted">
                      {segments(text).count} segment(s) SMS · validation
                      obligatoire avant envoi
                    </small>
                    <button className="primary wide">
                      Préparer la réponse
                    </button>
                  </form>
                )}
                {d.outgoing.map((m) => (
                  <p className="muted" key={m.id}>
                    {m.kind === "ACK" ? "Accusé de réception" : "Réponse"} ·{" "}
                    {m.status} · {m.attempts} tentative(s)
                  </p>
                ))}
              </>
            )}
            {tab === "actions" &&
              (d.actions.length ? (
                d.actions.map((a) => (
                  <div className="action-summary" key={a.id}>
                    <Lightbulb />
                    <div>
                      <h3>{a.title}</h3>
                      <p>
                        {a.owner_name} · {fmt(a.due)}
                      </p>
                      <Badge value={a.status} />
                    </div>
                  </div>
                ))
              ) : (
                <Empty text="Aucune action liée. Associez ce dossier depuis le registre des actions." />
              ))}
          </div>
        </section>
        <aside className="case-side">
          <section className="card">
            <h3>Suivi du dossier</h3>
            <dl>
              <dt>Échéance</dt>
              <dd>
                <Deadline d={d} />
                <small>{fmt(d.due)}</small>
              </dd>
              <dt>Responsable</dt>
              <dd>{d.owner_name || "Non attribué"}</dd>
              <dt>Thème</dt>
              <dd>{d.theme}</dd>
              <dt>Urgence</dt>
              <dd>
                <Badge value={d.urgency} />
              </dd>
              <dt>Réouvertures</dt>
              <dd>{d.reopen_count}</dd>
            </dl>
            {supervisor &&
              ["TRIE", "ATTRIBUE", "EN_TRAITEMENT"].includes(d.state) && (
                <button
                  className="primary wide"
                  onClick={() => setModal("assign")}
                >
                  Attribuer / réattribuer
                </button>
              )}
            {canWork && d.state === "ATTRIBUE" && (
              <button
                className="primary wide"
                onClick={() =>
                  change("/transitions", { state: "EN_TRAITEMENT" })
                }
              >
                Prendre en traitement
              </button>
            )}
            {canWork && d.state === "EN_TRAITEMENT" && (
              <button
                className="secondary wide"
                onClick={() => setModal({ kind: "referral" })}
              >
                Référer à un partenaire
              </button>
            )}
            {supervisor &&
              ["EN_TRAITEMENT", "REPONSE_TRANSMISE", "CLOTURE"].includes(
                d.state,
              ) && (
                <button
                  className="secondary wide"
                  onClick={() =>
                    setModal(d.state === "CLOTURE" ? "reopen" : "close")
                  }
                >
                  {d.state === "CLOTURE"
                    ? "Rouvrir le dossier"
                    : "Clôturer le dossier"}
                </button>
              )}
            {supervisor && d.state !== "CLOTURE" && (
              <button className="text-button" onClick={() => setModal("merge")}>
                Fusionner un doublon
              </button>
            )}
            {d.fusions.map((f) => (
              <button
                className="text-button"
                key={f.id}
                onClick={() => change("/fusion", { undo: f.id })}
              >
                Annuler la fusion de {f.source__reference}
              </button>
            ))}
          </section>
          <div className="protection-note">
            <ShieldCheck size={21} />
            <p>Les notes internes ne sont jamais envoyées à l’usager.</p>
          </div>
        </aside>
      </div>
      {modal && (
        <Modal
          title={
            modal === "qualification"
              ? "Qualification"
              : modal === "assign"
                ? "Attribution"
                : modal === "close"
                  ? "Clôture motivée"
                  : modal === "reopen"
                    ? "Réouverture"
                    : modal === "merge"
                      ? "Fusion réversible"
                      : modal.kind === "reject"
                        ? "Refuser la réponse"
                        : "Référencement"
          }
          close={() => setModal(null)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = Object.fromEntries(new FormData(e.target));
              if (modal === "qualification")
                change(
                  "/qualification",
                  { ...f, sensitive: f.sensitive === "on" },
                  "PATCH",
                );
              else if (modal === "assign")
                change("/transitions", {
                  state: "ATTRIBUE",
                  owner: Number(f.owner),
                  reason: f.reason,
                });
              else if (modal === "close" || modal === "reopen")
                change("/transitions", {
                  state: modal === "close" ? "CLOTURE" : "EN_TRAITEMENT",
                  reason: f.reason,
                });
              else if (modal === "merge") change("/fusion", f);
              else if (modal.kind === 'manual') change(`/reponses/${modal.reply}/transmission-manuelle`,f);
              else if (modal.kind === "reject")
                change(`/reponses/${modal.reply}/validation`, {
                  accepted: false,
                  ...f,
                });
              else change("/referencements", { ...f, id: modal.record?.id });
            }}
          >
            {modal === "qualification" ? (
              <>
                <Field label="Type">
                  <select name="type" defaultValue={d.type}>
                    {["QUESTION", "PLAINTE", "SUGGESTION", "SATISFACTION"].map(
                      (v) => (
                        <option key={v} value={v}>
                          {labels[v]}
                        </option>
                      ),
                    )}
                  </select>
                </Field>
                <Field label="Thème">
                  <select name="theme" defaultValue={d.theme}>
                    {config.themes.map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Urgence">
                  <select name="urgency" defaultValue={d.urgency}>
                    <option value="NORMALE">Normale</option>
                    <option value="URGENTE">Urgente</option>
                  </select>
                </Field>
                <label className="check sensitive-check">
                  <input type="checkbox" name="sensitive" /> Basculer dans le
                  circuit sensible (contenu masqué)
                </label>
              </>
            ) : modal === "assign" ? (
              <>
                <Field label="Gestionnaire">
                  <select name="owner" required defaultValue={d.owner || ""}>
                    <option value="" disabled>
                      Choisir un responsable
                    </option>
                    {users
                      .filter((u) => u.role === "R2")
                      .map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.first_name}
                        </option>
                      ))}
                  </select>
                </Field>
                <Field
                  label="Motif de réattribution"
                  name="reason"
                  required={!!d.owner}
                />
              </>
            ) : modal === "close" ? (
              <Field label="Motif">
                <select name="reason">
                  {[
                    "RESOLU",
                    "REPONDU_SANS_ACTION",
                    "REFERE",
                    "NON_JOIGNABLE",
                    "HORS_MANDAT",
                    "DOUBLON",
                  ].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </Field>
            ) : modal === "merge" ? (
              <>
                <Field
                  label="Identifiant UUID du dossier source"
                  name="source"
                  required
                />
                <Field label="Motif de fusion" name="reason" required />
              </>
            ) : modal.kind === 'manual' ? (<><div className="info">Aucun message automatique n’est envoyé. Attestez uniquement une réponse effectivement communiquée par le moyen consenti.</div><button type="button" className="text-button" onClick={()=>execute(async()=>{const c=await api('/dossiers/'+id+'/contact');notify(c.address);})}>Consulter le contact autorisé</button><Field label="Preuve de transmission (date, moyen et résultat)" name="evidence" required/></>) : ["reopen"].includes(modal) || modal.kind === "reject" ? (
              <Field label="Motif obligatoire" name="reason" required />
            ) : (
              <>
                <Field
                  label="Service ou partenaire destinataire"
                  name="recipient"
                  defaultValue={modal.record?.data.recipient}
                  required
                />
                <Field
                  label="Issue / suivi"
                  name="issue"
                  defaultValue={modal.record?.data.issue || "Issue attendue"}
                  required
                />
              </>
            )}
            <button className="primary wide">Enregistrer</button>
          </form>
        </Modal>
      )}
    </>
  );
}
