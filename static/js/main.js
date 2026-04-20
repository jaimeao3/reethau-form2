const form = document.getElementById('mainForm');
const notification = document.getElementById('notification');
const submitBtn = document.getElementById('submitBtn');

function showNotif(type, msg) {
  notification.className = `notification ${type}`;
  notification.textContent = type === 'success' ? '✅ ' + msg : '❌ ' + msg;
  notification.classList.remove('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (type === 'success') setTimeout(() => notification.classList.add('hidden'), 6000);
}

// Load dropdown ID dari spreadsheet
async function loadIDs() {
  const select = document.getElementById('id_request_select');
  if (!select) return;
  try {
    const res = await fetch('/get-all-ids');
    const result = await res.json();
    if (result.status === 'success' && result.ids.length > 0) {
      while (select.options.length > 1) select.remove(1);
      const unique = [...new Set(result.ids)];
      unique.forEach(id => {
        const opt = document.createElement('option');
        opt.value = id;
        opt.text = id;
        select.add(opt);
      });
    }
  } catch (e) {
    console.log('Gagal load IDs:', e);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadIDs);
} else {
  loadIDs();
}
window.addEventListener('load', loadIDs);

async function cariData() {
  const idRequest = document.getElementById('id_request_select').value;
  if (!idRequest) {
    showNotif('error', 'Pilih ID Request terlebih dahulu.');
    return;
  }

  const btn = document.getElementById('btnCari');
  btn.disabled = true;
  btn.textContent = '⏳ Mencari...';

  try {
    const res = await fetch(`/get-data-by-id/${idRequest}`);
    const result = await res.json();

    if (result.status === 'success') {
      const d = result.data;

      setField('posisi_lamaran',    d['Posisi Lamaran'] || '');
      setField('fpk_name',          d['FPK Name'] || '');
      setSelect('penempatan',       d['Penempatan'] || d['Lokasi Penempatan'] || '');
      setSelect('grade',            String(d['Grade'] || ''));
      setSelect('induk_perusahaan', d['Induk Perusahaan'] || d['PT Induk'] || '');
      setField('divisi',            d['Divisi'] || '');

      setSelect('budget_status',    d['Budget/Non Budget'] || '');
      setSelect('category',         d['Category'] || '');
      setField('detail_category',   d['Detail Category'] || '');
      setField('vacancy_request',   d['Vacancy Request'] || '');
      setSelect('form_fpk',         d['Form FPK'] || '');
      setField('link_form',         d['Link Form'] || '');

      setField('tgl_request_ptk',   formatDate(d['Tanggal Request PTK'] || ''));
      setField('tgl_approve_bod',   formatDate(d['Tanggal Approve BOD'] || ''));
      setField('jumlah_hari',       d['Jumlah Hari'] || '');
      setField('joined',            d['Joined'] || '');
      setField('cv_process',        d['CV Process'] || '');

      showNotif('success', `Data ID Request ${idRequest} ditemukan! Anda bisa edit sebelum simpan.`);
    } else {
      showNotif('error', `ID Request ${idRequest} tidak ditemukan.`);
    }
  } catch (err) {
    showNotif('error', 'Gagal menghubungi server.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🔍 Cari';
  }
}

function setField(name, value) {
  if (value === null || value === undefined) return;
  const el = document.querySelector(`[name="${name}"]`);
  if (el) el.value = value;
}

function setSelect(name, value) {
  if (!value) return;
  const el = document.querySelector(`[name="${name}"]`);
  if (!el) return;
  const str = value.toString().trim().toLowerCase();
  const match = Array.from(el.options).find(o =>
    o.value.toString().trim().toLowerCase() === str ||
    o.text.toString().trim().toLowerCase() === str
  );
  if (match) {
    el.value = match.value;
  } else {
    const opt = document.createElement('option');
    opt.value = value;
    opt.text = value;
    el.add(opt);
    el.value = value;
  }
}

function formatDate(val) {
  if (!val) return '';
  if (/^\d{4}-\d{2}-\d{2}$/.test(val)) return val;
  const d = new Date(val);
  if (!isNaN(d)) return d.toISOString().split('T')[0];
  return '';
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="btn-icon">⏳</span> Menyimpan...';
  notification.classList.add('hidden');

  try {
    const formData = new FormData(form);
    const res = await fetch('/submit', { method: 'POST', body: formData });
    const data = await res.json();

    if (data.status === 'success') {
      showNotif('success', data.message);
      form.reset();
    } else {
      showNotif('error', data.message);
    }
  } catch (err) {
    showNotif('error', 'Gagal menghubungi server. Pastikan Flask berjalan.');
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<span class="btn-icon">💾</span> Simpan ke Google Spreadsheet';
  }
});
