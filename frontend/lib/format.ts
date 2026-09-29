export function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleDateString("it-IT");
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString("it-IT", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate()
  )}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function isoFromLocalInput(value: string): string {
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    throw new Error("Data/ora non valida.");
  }
  return dt.toISOString();
}

export function humanFrequency(value: string | null | undefined): string {
  switch (value) {
    case "once_daily":
      return "1 volta al giorno";
    case "twice_daily":
      return "2 volte al giorno";
    case "three_times_daily":
      return "3 volte al giorno";
    case "four_times_daily":
      return "4 volte al giorno";
    case "every_other_day":
      return "a giorni alterni";
    case "weekly":
      return "settimanale";
    case "as_needed":
      return "al bisogno";
    case "custom":
      return "personalizzata";
    default:
      return value ?? "-";
  }
}

export function humanTherapyStatus(value: string | null | undefined): string {
  switch (value) {
    case "active":
      return "attiva";
    case "paused":
      return "in pausa";
    case "completed":
      return "completata";
    case "cancelled":
      return "annullata";
    default:
      return value ?? "-";
  }
}

export function humanReminderStatus(value: string | null | undefined): string {
  switch (value) {
    case "pending":
      return "da fare";
    case "done":
      return "fatto";
    case "snoozed":
      return "posticipato";
    case "cancelled":
      return "annullato";
    default:
      return value ?? "-";
  }
}

export function humanReminderType(value: string | null | undefined): string {
  switch (value) {
    case "medication":
      return "farmaco";
    case "appointment":
      return "visita/controllo";
    case "refill":
      return "rinnovo ricetta";
    case "measurement":
      return "misurazione";
    case "other":
      return "altro";
    default:
      return value ?? "-";
  }
}

export function therapyStatusClass(value: string | null | undefined): string {
  switch (value) {
    case "active":
      return "bg-green-100 text-green-800 border-green-200";
    case "paused":
      return "bg-amber-100 text-amber-800 border-amber-200";
    case "completed":
      return "bg-slate-100 text-slate-700 border-slate-200";
    case "cancelled":
      return "bg-red-100 text-red-800 border-red-200";
    default:
      return "bg-slate-100 text-slate-600 border-slate-200";
  }
}

export function reminderStatusClass(value: string | null | undefined): string {
  switch (value) {
    case "pending":
      return "bg-blue-100 text-blue-800 border-blue-200";
    case "done":
      return "bg-green-100 text-green-800 border-green-200";
    case "snoozed":
      return "bg-amber-100 text-amber-800 border-amber-200";
    case "cancelled":
      return "bg-red-100 text-red-800 border-red-200";
    default:
      return "bg-slate-100 text-slate-600 border-slate-200";
  }
}

export function reminderTypeClass(value: string | null | undefined): string {
  switch (value) {
    case "medication":
      return "bg-indigo-100 text-indigo-800 border-indigo-200";
    case "appointment":
      return "bg-purple-100 text-purple-800 border-purple-200";
    case "refill":
      return "bg-teal-100 text-teal-800 border-teal-200";
    case "measurement":
      return "bg-cyan-100 text-cyan-800 border-cyan-200";
    default:
      return "bg-slate-100 text-slate-600 border-slate-200";
  }
}