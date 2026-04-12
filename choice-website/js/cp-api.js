// ============================================================
// Choice Properties â Shared API Client (cp-api.js)
// All pages import this after config.js
// ============================================================

// Supabase client (lazy singleton)
// I-065: Guard against the defer/module race condition.
// config.js and supabase.min.js are loaded with `defer`. ES modules also defer,
// but the spec does not guarantee defer-script order relative to module execution
// across all browsers (particularly mobile Safari and older WebViews). If sb() is
// called before window.supabase or CONFIG is ready, we throw a clear error instead
// of a cryptic "Cannot read properties of undefined" that silently kills uploads.
let _sb = null;

function sb() {
  if (!_sb) {
    if (!window.supabase) {
      throw new Error(
        'Supabase SDK not loaded yet. ' +
        'Ensure supabase.min.js defer script runs before cp-api.js.'
      );
    }
    if (typeof CONFIG === 'undefined' || !CONFIG.SUPABASE_URL) {
      throw new Error(
        'CONFIG not ready. ' +
        'Ensure config.js defer script runs before cp-api.js.'
      );
    }
    _sb = window.supabase.createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_ANON_KEY, {
      auth: { persistSession: true, autoRefreshToken: true }
    });
  }
  return _sb;
}

// ââ Normalized return shape âââââââââââââââââââââââââââââââ
// Every public API method returns { ok, data, error }.
//   ok    â boolean, true on success
//   data  â payload on success, null on failure
//   error â human-readable string on failure, null on success
//
// Internal helper â wraps a Supabase { data, error } pair.
function _ok(data, error) {
  if (error) return { ok: false, data: null, error: error.message || String(error) };
  return { ok: true, data: data ?? null, error: null };
}

// ââ Auth helpers ââââââââââââââââââââââââââââââââââââââââââ
const Auth = {
  async getUser()       { const { data } = await sb().auth.getUser(); return data?.user || null; },
  async getSession()    { const { data } = await sb().auth.getSession(); return data?.session || null; },
  // Returns a server-verified access token, or null if the session is invalid.
  // Strategy:
  //   1. Force-refresh the token via refreshSession() to bypass any stale cached token.
  //   2. Confirm the token actually works by calling getUser() (same check the edge function runs).
  //   3. If either step fails, sign out locally to clear the broken session, then return null.
  //      The caller should then redirect to the login page.
  async getAccessToken() {
    // Always force-refresh to avoid returning an expired cached access_token.
    // getSession() can return a stale token on slow connections when auto-refresh timed out.
    let token = null;
    let refreshFailed = false;
    try {
      const { data: rd, error: re } = await sb().auth.refreshSession();
      token = rd?.session?.access_token ?? null;
      // I-064: Distinguish network failure from auth failure.
      // refreshSession() throws on network error but returns { error } on auth error.
      // Only flag as auth failure when the server actually rejected the token.
      if (!token && re) refreshFailed = true;
    } catch { /* network failure â fall through to cached session */ }

    // Fall back to cached session if refresh failed (e.g. no network at all)
    if (!token) {
      try {
        const { data: sd } = await sb().auth.getSession();
        token = sd?.session?.access_token ?? null;
      } catch { /* ignore */ }
    }

    if (!token) {
      // I-064: Only sign out if we have confirmed the token is auth-rejected,
      // not just because the network was slow or offline. Signing out on a
      // network hiccup during upload destroys the session and loses form state.
      if (refreshFailed) {
        await sb().auth.signOut().catch(() => {}); // clear confirmed-invalid session
      }
      return null;
    }

    // Server-side verify: confirm the edge function will accept this token.
    // This is the same check requireAuth() runs inside the edge function.
    try {
      const { data: ud, error: ue } = await sb().auth.getUser(token);
      if (ue || !ud?.user) {
        await sb().auth.signOut().catch(() => {}); // purge broken session
        return null;
      }
    } catch {
      // Network too slow to verify â trust the refreshed token and let the upload try.
      // If it fails, the improved error handler will catch it.
    }

    return token;
  },
  async signOut() {
    await sb().auth.signOut();
    // Route to the correct login page based on current URL path
    const path = location.pathname;
    if (path.includes('/admin/'))  { location.href = '/admin/login.html'; }
    else if (path.includes('/apply/')) { location.href = '/apply/login.html'; }
    else { location.href = '/landlord/login.html'; }
  },
  async isAdmin()       {
    const user = await Auth.getUser();
    if (!user) return false;
    const { data } = await sb().from('admin_roles').select('id').eq('user_id', user.id).maybeSingle();
    return !!data;
  },
  async requireLandlord(redirectTo = '../landlord/login.html') {
    const user = await Auth.getUser();
    if (!user) { location.href = redirectTo; return null; }
    const { data } = await sb().from('landlords').select('*').eq('user_id', user.id).maybeSingle();
    if (!data) { location.href = redirectTo; return null; }
    return data;
  },
  async requireAdmin(redirectTo = '../admin/login.html') {
    const isAdmin = await Auth.isAdmin();
    if (!isAdmin) { location.href = redirectTo; return false; }
    return true;
  },
};

// ââ Edge Function caller ââââââââââââââââââââââââââââââââââ
// Returns { ok, data, error } â never throws.
async function callEdgeFunction(name, payload) {
  try {
    const session = await Auth.getSession();
    const token = session?.access_token || CONFIG.SUPABASE_ANON_KEY;
    const res = await fetch(`${CONFIG.SUPABASE_URL}/functions/v1/${name}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'apikey': CONFIG.SUPABASE_ANON_KEY,
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    let json = {};
    try { json = await res.json(); } catch (_) {}
    if (!res.ok) {
      const msg = json.error || json.message || res.statusText || `HTTP ${res.status}`;
      return { ok: false, data: null, error: msg };
    }
    // Edge Functions return { success, error, ...payload } â unwrap into our shape.
    if ('success' in json) {
      if (!json.success) return { ok: false, data: null, error: json.error || 'Unknown error' };
      const { success: _s, error: _e, ...rest } = json;
      return { ok: true, data: Object.keys(rest).length ? rest : null, error: null };
    }
    return { ok: true, data: json, error: null };
  } catch (err) {
    return { ok: false, data: null, error: err.message || String(err) };
  }
}
// ââ Properties API ââââââââââââââââââââââââââââââââââââââââ
const Properties = {
  // getListings â server-side filtered, sorted, paginated query for the listings page.
  // filters: { q, type, beds, min_beds, min_baths, min_rent, max_rent, pets, parking, available, sort, page, per_page }
  // Returns { ok, data: { rows, total, page, per_page, total_pages }, error }
  async getListings(filters = {}) {
    const PAGE_SIZE = filters.per_page || 24;
    const page = Math.max(1, filters.page || 1);
    const from = (page - 1) * PAGE_SIZE;
    const to   = from + PAGE_SIZE - 1;

    let q = sb()
      .from('properties')
      .select('*, landlords(contact_name, business_name, avatar_url, verified)', { count: 'exact' })
      .eq('status', 'active');

    // Text search â uses the GIN-indexed search_tsv generated column.
    // Falls back to ilike on title only if the term contains characters
    // that would break tsquery (e.g. bare punctuation).
    if (filters.q) {
      const term = filters.q.trim();
      const safeForTs = /^[\w\s\-']+$/.test(term);
      if (safeForTs) {
        q = q.textSearch('search_tsv', term, { type: 'websearch', config: 'english' });
      } else {
        q = q.ilike('title', `%${term}%`);
      }
    }

    // Property type pill (apartment / house / condo / townhouse)
    if (filters.type && filters.type !== 'all' && !['pets','parking','available'].includes(filters.type)) {
      q = q.eq('property_type', filters.type);
    }
    // Special pills
    if (filters.type === 'pets')      q = q.eq('pets_allowed', true);
    if (filters.type === 'parking')   q = q.not('parking', 'is', null).neq('parking', '').neq('parking', 'None');
    // C1 FIX: "Move-in Ready" must also match properties where available_date IS NULL
    // (those are immediately available â landlords who didn't set a date).
    if (filters.type === 'available') q = q.or(`available_date.is.null,available_date.lte.${new Date().toISOString().slice(0,10)}`);

    // Bedrooms â exact match from quick filter, gte from advanced min_beds
    if (filters.beds !== undefined && filters.beds !== '') {
      const beds = parseInt(filters.beds);
      if (beds === 4) { q = q.gte('bedrooms', 4); }
      else            { q = q.eq('bedrooms', beds); }
    } else if (filters.min_beds !== undefined && filters.min_beds !== '') {
      q = q.gte('bedrooms', parseInt(filters.min_beds));
    }

    // Bathrooms
    if (filters.min_baths !== undefined && filters.min_baths !== '') {
      q = q.gte('bathrooms', parseFloat(filters.min_baths));
    }

    // Rent range
    if (filters.min_rent !== undefined && filters.min_rent !== '') {
      q = q.gte('monthly_rent', parseInt(filters.min_rent));
    }
    if (filters.max_rent !== undefined && filters.max_rent !== '') {
      q = q.lte('monthly_rent', parseInt(filters.max_rent));
    }

    // Laundry type filter
    if (filters.laundry_type) q = q.eq('laundry_type', filters.laundry_type);

    // Heating type filter
    if (filters.heating_type) q = q.eq('heating_type', filters.heating_type);

    // Pet type filter â checks if pet_types_allowed array contains the requested type
    if (filters.pet_type) q = q.contains('pet_types_allowed', [filters.pet_type]);

    // Sort
    switch (filters.sort) {
      case 'price_asc':  q = q.order('monthly_rent', { ascending: true });  break;
      case 'price_desc': q = q.order('monthly_rent', { ascending: false }); break;
      case 'beds_desc':  q = q.order('bedrooms', { ascending: false });      break;
      default:           q = q.order('created_at', { ascending: false });    break;
    }

    // Pagination
    q = q.range(from, to);

    const { data, error, count } = await q;
    if (error) return { ok: false, data: null, error: error.message };
    const total = count ?? 0;
    return {
      ok: true,
      error: null,
      data: {
        rows:        data || [],
        total,
        page,
        per_page:    PAGE_SIZE,
        total_pages: Math.ceil(total / PAGE_SIZE),
      },
    };
  },

  async getAll(filters = {}) {
    let q = sb().from('properties').select('*, landlords(contact_name, business_name, avatar_url, verified)').order('created_at', { ascending: false });
    if (filters.status)    q = q.eq('status', filters.status);
    if (filters.landlord)  q = q.eq('landlord_id', filters.landlord);
    if (filters.bedrooms !== undefined && filters.bedrooms !== '') q = q.gte('bedrooms', filters.bedrooms);
    if (filters.max_rent)  q = q.lte('monthly_rent', filters.max_rent);
    if (filters.state)     q = q.eq('state', filters.state);
    const { data, error } = await q;
    return _ok(data || [], error);
  },
  async getOne(id) {
    const { data, error } = await sb().from('properties').select('*, landlords(*)').eq('id', id).single();
    if (data && data.landlords && !data.landlords.avatar_url) {
      data.landlords.avatar_url = '/assets/avatar-placeholder.png';
    }
    return _ok(data, error);
  },
  // I-026: NOTE â this method is not currently used by new-listing.html.
  // That page calls generate_property_id() RPC + .insert() directly so it
  // can cache the propId in localStorage for retry-safe photo uploads.
  // If you update the insert payload shape here, update new-listing.html too.
  // Future: accept an optional pre-generated id param to unify both paths.
  async create(payload)   {
    const { data: newId, error: idErr } = await sb().rpc('generate_property_id');
    if (idErr || !newId) return { ok: false, data: null, error: idErr?.message || 'Failed to generate property ID' };
    const { data, error } = await sb().from('properties').insert({ ...payload, id: newId }).select().single();
    return _ok(data, error);
  },
  async update(id, payload) {
    const { data, error } = await sb().from('properties').update(payload).eq('id', id).select().single();
    return _ok(data, error);
  },
  async delete(id)        { return sb().from('properties').delete().eq('id', id); },
  async incrementView(id) { return sb().rpc('increment_counter', { p_table: 'properties', p_id: id, p_column: 'views_count' }); },
};

// ââ Saved Properties API ââââââââââââââââââââââââââââââââââ
// C4 FIX: Connects the heart/save button to the saved_properties DB table
// for authenticated users (saves persist across devices).  Falls back to
// localStorage for anonymous visitors so the experience still works.
// The DB trigger trg_saves_count() auto-updates properties.saves_count on INSERT/DELETE.
const SavedProperties = {
  // Load saved property IDs for the current user.
  // Authenticated â DB query; anonymous â localStorage.
  // Always returns a Set<string>.
  async getIds() {
    const user = await Auth.getUser();
    if (!user) return new Set(JSON.parse(localStorage.getItem('cp_saved') || '[]'));
    const { data, error } = await sb()
      .from('saved_properties')
      .select('property_id')
      .eq('user_id', user.id);
    if (error) return new Set(JSON.parse(localStorage.getItem('cp_saved') || '[]'));
    return new Set((data || []).map(r => r.property_id));
  },

  // Toggle save state for one property.
  // Returns { saved: boolean }.
  async toggle(propertyId) {
    const user = await Auth.getUser();
    if (!user) {
      // Anonymous â localStorage only
      const ids = new Set(JSON.parse(localStorage.getItem('cp_saved') || '[]'));
      const saved = !ids.has(propertyId);
      if (saved) ids.add(propertyId); else ids.delete(propertyId);
      localStorage.setItem('cp_saved', JSON.stringify([...ids]));
      return { saved };
    }
    // Authenticated â check DB first to determine current state
    const { data: existing } = await sb()
      .from('saved_properties')
      .select('id')
      .eq('user_id', user.id)
      .eq('property_id', propertyId)
      .maybeSingle();
    let saved;
    if (existing) {
      // Currently saved â unsave (delete row; trigger decrements saves_count)
      await sb().from('saved_properties').delete().eq('id', existing.id);
      saved = false;
    } else {
      // Not saved â save (insert row; trigger increments saves_count)
      await sb().from('saved_properties').insert({ user_id: user.id, property_id: propertyId });
      saved = true;
    }
    // Keep localStorage in sync so anonymous fallback stays accurate
    const ids = new Set(JSON.parse(localStorage.getItem('cp_saved') || '[]'));
    if (saved) ids.add(propertyId); else ids.delete(propertyId);
    localStorage.setItem('cp_saved', JSON.stringify([...ids]));
    return { saved };
  },
};

// ââ Inquiries API âââââââââââââââââââââââââââââââââââââââââ
const Inquiries = {
  async submit(payload)       {
    // Client-side throttle: max 1 inquiry per 60 s per browser session.
    // The send-inquiry Edge Function enforces a stricter server-side IP rate limit
    // (5 per 5 min), so this is just a fast-path guard for accidental double-submits.
    const THROTTLE_KEY = 'cp_inquiry_last';
    const last = parseInt(localStorage.getItem(THROTTLE_KEY) || '0', 10);
    if (Date.now() - last < 60000) {
      return { ok: false, data: null, error: 'Please wait a moment before sending another inquiry.' };
    }
    // C-04 FIX: All inquiry submissions now go through the Edge Function only.
    // The Edge Function uses the service-role key for the DB insert, so the anon
    // role no longer needs INSERT on the inquiries table. This closes the bypass
    // where anyone with the public anon key could insert directly via the REST API,
    // circumventing server-side rate limiting entirely.
    const result = await callEdgeFunction('send-inquiry', {
      type:            'new_inquiry',
      tenant_name:     payload.tenant_name,
      tenant_email:    payload.tenant_email,
      tenant_language: payload.tenant_language || (typeof localStorage !== 'undefined' ? localStorage.getItem('cp_lang') : null) || 'en',
      message:         payload.message,
      property_id:     payload.property_id,
      tenant_phone:    payload.tenant_phone || null,
      // Pass all remaining fields so the Edge Function can do the full insert
      insert_payload:  payload,
    });
    if (result?.ok) {
      localStorage.setItem(THROTTLE_KEY, String(Date.now()));
    }
    return result;
  },
  async getForLandlord(landlordId) {
    // Single query: PostgREST !inner join filters inquiries to only those
    // whose property.landlord_id matches â no separate property-ID fetch needed.
    const { data, error } = await sb()
      .from('inquiries')
      .select('*, properties!inner(id, title, address, landlord_id)')
      .eq('properties.landlord_id', landlordId)
      .order('created_at', { ascending: false });
    return _ok(data || [], error);
  },
  async markRead(id) { return sb().from('inquiries').update({ read: true }).eq('id', id); },
};

// ââ Landlords API âââââââââââââââââââââââââââââââââââââââââ
const Landlords = {
  async getProfile(userId)  {
    const { data, error } = await sb().from('landlords').select('*').eq('user_id', userId).maybeSingle();
    return _ok(data, error);
  },
  async update(id, payload) {
    const { data, error } = await sb().from('landlords').update(payload).eq('id', id).select().single();
    return _ok(data, error);
  },
  async getAll(filters = {})            {
    const perPage = filters.perPage || 50;
    const page    = filters.page    || 0;
    const { data, error, count } = await sb()
      .from('landlords')
      .select('*, properties(count)', { count: 'exact' })
      .order('created_at', { ascending: false })
      .range(page * perPage, (page + 1) * perPage - 1);
    if (error) return { ok: false, data: null, error: error.message };
    return { ok: true, data: data || [], error: null, count: count || 0, page, perPage };
  },
};

// ââ Email Logs API ââââââââââââââââââââââââââââââââââââââââ
const EmailLogs = {
  async getAll(filters = {}) {
    const perPage = filters.perPage || 50;
    const page    = filters.page    || 0;
    let q = sb().from('email_logs')
      .select('*', { count: 'exact' })
      .order('created_at', { ascending: false })
      .range(page * perPage, (page + 1) * perPage - 1);
    if (filters.app_id)  q = q.eq('app_id', filters.app_id);
    if (filters.type)    q = q.eq('type', filters.type);
    if (filters.status)  q = q.eq('status', filters.status);
    const { data, error, count } = await q;
    if (error) return { ok: false, data: null, error: error.message };
    return { ok: true, data: data || [], error: null, count: count || 0, page, perPage };
  },
};


// ââ UI utilities ââââââââââââââââââââââââââââââââââââââââââ
const UI = {
  fmt: {
    currency: (n) => `$${parseFloat(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
    date:     (d) => d ? new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : 'â',
    dateTime: (d) => d ? new Date(d).toLocaleString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'â',
    status:   (s) => s ? s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'â',
    phone:    (p) => p ? p.replace(/(\d{3})(\d{3})(\d{4})/, '($1) $2-$3') : '',
  },
  statusBadge(status) {
    const map = {
      pending:      'badge-warning',
      under_review: 'badge-info',
      approved:     'badge-success',
      denied:       'badge-danger',
      withdrawn:    'badge-secondary',
      waitlisted:   'badge-secondary',
    };
    return `<span class="badge ${map[status] || 'badge-secondary'}">${UI.fmt.status(status)}</span>`;
  },
  paymentBadge(status) {
    const map = { unpaid:'badge-danger', paid:'badge-success', waived:'badge-info', refunded:'badge-warning' };
    return `<span class="badge ${map[status] || 'badge-secondary'}">${UI.fmt.status(status)}</span>`;
  },
  leaseBadge(status) {
    const map = { none:'badge-secondary', sent:'badge-info', signed:'badge-success', awaiting_co_sign:'badge-warning', co_signed:'badge-success', voided:'badge-danger', expired:'badge-warning' };
    return `<span class="badge ${map[status] || 'badge-secondary'}">${UI.fmt.status(status)}</span>`;
  },
  toast(msg, type = 'info', duration = 4000) {
    const t = document.createElement('div');
    t.className = `cp-toast cp-toast-${type}`;
    t.textContent = msg;
    document.body.appendChild(t);
    requestAnimationFrame(() => t.classList.add('show'));
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, duration);
  },
  loading(el, on) {
    if (on) { el.dataset.origText = el.textContent; el.disabled = true; el.textContent = 'Loadingâ¦'; }
    else    { el.textContent = el.dataset.origText || el.textContent; el.disabled = false; }
  },
  // Promise-based confirm dialog â replaces native confirm() with inline modal
  cpConfirm(message, { confirmLabel = 'Confirm', cancelLabel = 'Cancel', danger = false } = {}) {
    return new Promise((resolve) => {
      const existing = document.getElementById('_cpConfirmOverlay');
      if (existing) existing.remove();

      const overlay = document.createElement('div');
      overlay.id = '_cpConfirmOverlay';
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:99999;display:flex;align-items:center;justify-content:center;padding:20px;';

      const btnColor = danger ? '#dc2626' : 'var(--gold,#c9a84c)';
      overlay.innerHTML = `
        <div style="background:var(--surface,#1a2332);border:1px solid var(--border,#2a3a4a);border-radius:12px;max-width:440px;width:100%;padding:28px;box-shadow:0 24px 64px rgba(0,0,0,.5);">
          <div style="font-size:.95rem;font-weight:600;color:var(--text,#e8eaf0);line-height:1.6;margin-bottom:24px;">${message}</div>
          <div style="display:flex;justify-content:flex-end;gap:10px;">
            <button id="_cpConfirmCancel" style="background:transparent;border:1px solid var(--border,#2a3a4a);color:var(--muted,#8892a2);border-radius:6px;padding:9px 18px;font-size:.82rem;font-weight:600;cursor:pointer;">${cancelLabel}</button>
            <button id="_cpConfirmOk" style="background:${btnColor};border:none;color:${danger ? '#fff' : '#0e1825'};border-radius:6px;padding:9px 18px;font-size:.82rem;font-weight:600;cursor:pointer;">${confirmLabel}</button>
          </div>
        </div>`;

      document.body.appendChild(overlay);

      const cleanup = (val) => { overlay.remove(); resolve(val); };
      document.getElementById('_cpConfirmOk').addEventListener('click', () => cleanup(true));
      document.getElementById('_cpConfirmCancel').addEventListener('click', () => cleanup(false));
      overlay.addEventListener('click', (e) => { if (e.target === overlay) cleanup(false); });
    });
  },

  // ââ LQIP â returns a tiny blurred ImageKit URL for blur-up loading âââââââââ
  // Usage: img.style.backgroundImage = `url(${CP.UI.lqipUrl(url)})`;
  // Returns null if ImageKit is not configured (safe to ignore).
  lqipUrl(url) {
    if (!url || !window.CONFIG || !CONFIG.IMAGEKIT_URL || CONFIG.IMAGEKIT_URL === '') return null;
    const base = url.startsWith(CONFIG.IMAGEKIT_URL)
      ? url.replace(/\/tr:[^/]+/, '')
      : CONFIG.IMAGEKIT_URL + '/' + encodeURIComponent(url);
    return base.replace(CONFIG.IMAGEKIT_URL, CONFIG.IMAGEKIT_URL + '/tr:w-30,bl-20,q-20,f-webp');
  },

  // ââ Table skeleton rows (shimmer placeholders while data loads) ââââââââââ
  // Usage: tbody.innerHTML = CP.UI.skeletonRows(5, 6);
  // cols  â number of <td> cells per row (match your table's column count)
  // rows  â number of placeholder rows to show (default 5)
  skeletonRows(rows = 5, cols = 4) {
    const cells = Array(cols).fill('<td><div class="sk-cell"></div></td>').join('');
    return Array(rows).fill(`<tr class="sk-row">${cells}</tr>`).join('');
  },

  // ââ Empty state for tables (no results) âââââââââââââââââââââââââââââââââ
  // Usage (table): tbody.innerHTML = CP.UI.emptyState('No applications yet', 'ð', cols);
  // Usage (div):   container.innerHTML = CP.UI.emptyState('No messages yet', 'ð¬');
  // If cols is provided, wraps in a single <tr><td colspan="cols"> for table use.
  emptyState(message, icon = 'ð­', cols = 0) {
    const inner = `<div class="cp-empty-state"><span class="cp-empty-icon">${icon}</span><span class="cp-empty-msg">${message}</span></div>`;
    return cols ? `<tr><td colspan="${cols}">${inner}</td></tr>` : inner;
  },

  // ââ Error state for tables / divs (load failure) âââââââââââââââââââââââââ
  // Usage (table): tbody.innerHTML = CP.UI.errorState('Failed to load data', cols);
  // Usage (div):   container.innerHTML = CP.UI.errorState('Failed to load data');
  errorState(message = 'Failed to load data. Please refresh and try again.', cols = 0) {
    const inner = `<div class="cp-error-state"><span class="cp-error-icon">â ï¸</span><span class="cp-error-msg">${message}</span></div>`;
    return cols ? `<tr><td colspan="${cols}">${inner}</td></tr>` : inner;
  },
};

// ââ XSS-safe HTML escape âââââââââââââââââââââââââââââââââ
// Use esc() whenever injecting user-supplied text into innerHTML.
function esc(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ââ Landlord helper functions âââââââââââââââââââââââââââââ
// Defined here so they live in one place and are accessible
// via both window.CP (inline scripts) and ES named exports below.

function buildApplyURL(property) {
  // ââ Layer 1: sessionStorage (same-origin only) ââââââââââââââââââââââââââââ
  // Stores full context for same-origin use. Cross-origin (external form)
  // cannot read sessionStorage â it relies entirely on the URL params below.
  // landlord_id is included here only â never in the URL.
  try {
    sessionStorage.setItem('cp_property_context', JSON.stringify({
      id:               property.id,
      title:            property.title,
      address:          property.address,
      city:             property.city,
      state:            property.state,
      zip:              property.zip              || '',
      monthly_rent:     property.monthly_rent     || null,
      security_deposit: property.security_deposit || null,
      application_fee:  property.application_fee  || 0,
      available_date:   property.available_date   || null,
      landlord_id:      property.landlord_id      || null,
      bedrooms:         property.bedrooms         || null,
      bathrooms:        property.bathrooms        || null,
      lease_terms:      property.lease_terms      || [],
      minimum_lease_months: property.minimum_lease_months || null,
      pets_allowed:     property.pets_allowed     ?? false,
      pet_types_allowed:property.pet_types_allowed|| [],
      pet_weight_limit: property.pet_weight_limit || null,
      pet_deposit:      property.pet_deposit      || null,
      pet_details:      property.pet_details      || null,
      smoking_allowed:  property.smoking_allowed  ?? false,
      utilities_included: property.utilities_included || [],
      parking:          property.parking          || null,
      parking_fee:      property.parking_fee      || null,
      garage_spaces:    property.garage_spaces    || null,
      ev_charging:      property.ev_charging      || null,
      laundry_type:     property.laundry_type     || null,
      heating_type:     property.heating_type     || null,
      cooling_type:     property.cooling_type     || null,
      last_months_rent: property.last_months_rent || null,
      admin_fee:        property.admin_fee        || null,
      move_in_special:  property.move_in_special  || null,
    }));
  } catch (_) {
    // sessionStorage unavailable (private browsing) â URL params are the fallback.
  }

  // ââ Layer 2: URL query params (cross-origin safe) âââââââââââââââââââââââââ
  // Structured, machine-readable values so the external GAS form can:
  //   â¢ Pre-fill fields from the property data
  //   â¢ Restrict choices to only what this property allows (lease terms, pets, etc.)
  //   â¢ Enforce move-in date minimums from available_date
  //   â¢ Show/hide sections based on boolean flags (pets, smoking)
  //
  // landlord_id is NEVER included â resolved server-side from property_id.
  // Arrays use pipe "|" as a separator so GAS can split on it easily.
  const p = new URLSearchParams();

  // ââ Identity & location âââââââââââââââââââââââââââââââââââââââââââââââââââ
  p.set('id',    property.id);
  if (property.title)   p.set('pn',    property.title.substring(0, 120));
  if (property.address) p.set('addr',  property.address.substring(0, 100));
  if (property.city)    p.set('city',  property.city);
  if (property.state)   p.set('state', property.state);
  if (property.zip)     p.set('zip',   property.zip);

  // ââ Financials ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
  if (property.monthly_rent)     p.set('rent',    property.monthly_rent);
  if (property.security_deposit) p.set('deposit', property.security_deposit);
  p.set('fee', property.application_fee != null ? property.application_fee : 0); // 9C-1: always send fee, even if zero

  // ââ Unit details ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
  if (property.bedrooms  != null) p.set('beds',  property.bedrooms);
  if (property.bathrooms != null) p.set('baths', property.bathrooms);

  // ââ Availability & lease terms ââââââââââââââââââââââââââââââââââââââââââââ
  // avail: ISO date string â GAS uses this as the minimum allowed move-in date.
  // terms: pipe-separated list of allowed lease term options â GAS builds a
  //        constrained dropdown/radio group from this, hiding disallowed options.
  // min_months: numeric minimum â fallback when lease_terms array is empty.
  if (property.available_date) p.set('avail', property.available_date);

  if (property.lease_terms && property.lease_terms.length) {
    const terms = Array.isArray(property.lease_terms)
      ? property.lease_terms.join('|')
      : property.lease_terms;
    p.set('terms', terms);
  } else if (property.minimum_lease_months) {
    p.set('terms',      `${property.minimum_lease_months} months`);
    p.set('min_months', property.minimum_lease_months);
  }
  if (property.minimum_lease_months) p.set('min_months', property.minimum_lease_months);

  // ââ Pet policy ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
  // pets: boolean string "true"/"false" â GAS shows/hides the pet section.
  // pet_types: pipe-separated allowed pet types â GAS uses for validation.
  // pet_weight: numeric max weight in lbs â GAS validates weight input against it.
  // pet_deposit: numeric â GAS displays as expected cost in the pet section.
  p.set('pets', property.pets_allowed ? 'true' : 'false');
  if (property.pets_allowed) {
    if (property.pet_types_allowed && property.pet_types_allowed.length) {
      const types = Array.isArray(property.pet_types_allowed)
        ? property.pet_types_allowed.join('|')
        : property.pet_types_allowed;
      p.set('pet_types', types);
    }
    if (property.pet_weight_limit) p.set('pet_weight',  property.pet_weight_limit);
    if (property.pet_deposit)      p.set('pet_deposit', property.pet_deposit);
    if (property.pet_details)      p.set('pet_details', property.pet_details.substring(0, 200));
  }

  // ââ Smoking policy ââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
  // smoking: boolean string "true"/"false" â GAS pre-sets and locks the field.
  p.set('smoking', property.smoking_allowed ? 'true' : 'false');

  // ââ Utilities & parking âââââââââââââââââââââââââââââââââââââââââââââââââââ
  // utilities: pipe-separated list â GAS displays as included utilities context.
  // parking: text value â GAS displays as parking info context.
  if (property.utilities_included && property.utilities_included.length) {
    const utils = Array.isArray(property.utilities_included)
      ? property.utilities_included.join('|')
      : property.utilities_included;
    p.set('utilities', utils);
  }
  if (property.parking)     p.set('parking',     property.parking);
  if (property.parking_fee) p.set('parking_fee', property.parking_fee);
  if (property.garage_spaces) p.set('garage_spaces', property.garage_spaces);
  if (property.ev_charging && property.ev_charging !== 'none') p.set('ev_charging', property.ev_charging);
  if (property.laundry_type) p.set('laundry_type', property.laundry_type);
  if (property.heating_type) p.set('heating_type', property.heating_type);
  if (property.cooling_type) p.set('cooling_type', property.cooling_type);

  // ââ Financial move-in costs âââââââââââââââââââââââââââââââââââââââââââââââââââ
  if (property.last_months_rent) p.set('last_months_rent', property.last_months_rent);
  if (property.admin_fee)        p.set('admin_fee',        property.admin_fee);
  if (property.move_in_special)  p.set('move_in_special',  property.move_in_special.substring(0, 200));

  // ââ Resolve target base URL âââââââââââââââââââââââââââââââââââââââââââââââ
  const base = (typeof CONFIG !== 'undefined' && CONFIG.APPLY_FORM_URL)
    ? CONFIG.APPLY_FORM_URL
    : 'https://apply-choice-properties.pages.dev';

  // 9C-2: pass current page URL so apply form can show 'Back to listing' link
  try { p.set('source', window.location.href.substring(0, 300)); } catch (_) {}

    // B2: Guard URL length — if over 7000 chars, drop optional free-text fields and retry
      let _finalUrl = `${base}?${p.toString()}`;
      if (_finalUrl.length > 7000) {
        console.warn('[buildApplyURL] URL length ' + _finalUrl.length + ' chars — dropping optional params to reduce size');
        ['pet_details', 'move_in_special', 'source', 'utilities', 'parking', 'laundry_type', 'heating_type', 'cooling_type'].forEach(k => p.delete(k));
        _finalUrl = `${base}?${p.toString()}`;
        if (_finalUrl.length > 7000) {
          console.warn('[buildApplyURL] URL still ' + _finalUrl.length + ' chars after reduction — may truncate on some browsers');
        }
      }
      return _finalUrl;
    }

async function incrementCounter(table, id, column) {
  return sb().rpc('increment_counter', { p_table: table, p_id: id, p_column: column });
}

async function getSession()         { return Auth.getSession(); }
async function getLandlordProfile() { const user = await Auth.getUser(); if (!user) return null; return (await Landlords.getProfile(user.id)).data; }
async function requireAuth(r)       { return Auth.requireLandlord(r); }
async function signIn(e, p)         { const { data, error } = await sb().auth.signInWithPassword({ email: e, password: p }); if (error) throw error; return data; }
async function signUp(email, password, profile) {
  const { data, error } = await sb().auth.signUp({ email, password, options: { data: profile } });
  if (error) throw error;
  if (data.user) {
    const { error: pe } = await sb().from('landlords').insert({ user_id: data.user.id, email, contact_name: profile.contact_name, business_name: profile.business_name || null, phone: profile.phone || null, account_type: profile.account_type || 'landlord', avatar_url: profile.avatar_url || null });
    if (pe) {
      // Auth user was created but profile insert failed. Sign out the orphaned session
      // so the user can retry registration cleanly without being stuck in a half-logged-in state.
      await sb().auth.signOut();
      throw new Error('Account setup failed: ' + pe.message + '. Please try registering again.');
    }
  }
  return data;
}
async function signOut() {
  await sb().auth.signOut();
  const isAdminPath = window.location.pathname.includes('/admin/');
  window.location.href = isAdminPath ? '/admin/login.html' : '/landlord/login.html';
}
async function resetPassword(email, redirectPath = '/landlord/login.html') { const { error } = await sb().auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}${redirectPath}` }); if (error) throw error; }
async function updateNav() {
  const session    = await Auth.getSession();
  const authLink   = document.getElementById('navAuthLink');
  const drawerLink = document.getElementById('drawerAuthLink');
  if (session) {
    if (authLink)   { authLink.href   = '/landlord/dashboard.html'; authLink.textContent   = 'My Dashboard'; }
    if (drawerLink) { drawerLink.href = '/landlord/dashboard.html'; drawerLink.textContent = 'My Dashboard'; }
  } else {
    if (authLink)   { authLink.href   = '/landlord/register.html'; authLink.textContent   = 'List Your Property'; }
    if (drawerLink) { drawerLink.href = '/landlord/login.html';    drawerLink.textContent = 'Landlord Login'; }
  }
}

// ââ Single source of truth: window.CP ââââââââââââââââââââ
// Admin pages, apply.js, and inline <script> blocks all read
// from window.CP. ES exports below are thin re-exports â they
// add no logic of their own, so there is only ONE place to
// edit when adding or changing any function.
window.CP_esc = esc;
window.CP = {
    // NOTE: Applications object removed â all application management is
    // handled by the external GAS system at apply-choice-properties.pages.dev
    sb, Auth, Properties, SavedProperties, Inquiries, Landlords, EmailLogs, UI,
    buildApplyURL, incrementCounter,
    getSession, getLandlordProfile, requireAuth,
    signIn, signUp, signOut, resetPassword, updateNav,
  };

// ââ ES Module exports âââââââââââââââââââââââââââââââââââââ
// Landlord pages and property.html import these by name.
// Each export delegates to the function defined above â no
// duplicated logic, no separate window.* assignments needed.
export const supabase = sb();
export { buildApplyURL, incrementCounter, getSession, getLandlordProfile, requireAuth, signIn, signUp, signOut, resetPassword, updateNav };
