const form        = document.getElementById('lead-form');
const nameInput   = document.getElementById('name');
const phoneInput  = document.getElementById('phone');
const consent     = form.querySelector('input[type="checkbox"]');
const submitBtn   = form.querySelector('button[type="submit"]');
const successBlock = document.getElementById('form-success');

/* ── Авто-формат телефона ──────────────────────────────── */
phoneInput.addEventListener('focus', function () {
  if (this.value === '') this.value = '+7 ';
});

phoneInput.addEventListener('input', function () {
  let digits = this.value.replace(/\D/g, '');

  if (digits.startsWith('8')) digits = '7' + digits.slice(1);
  if (digits.length > 0 && !digits.startsWith('7')) digits = '7' + digits;
  digits = digits.slice(0, 11);

  let out = '';
  if (digits.length > 0)  out = '+7';
  if (digits.length > 1)  out += ' (' + digits.slice(1, 4);
  if (digits.length >= 4) out += ') ' + digits.slice(4, 7);
  if (digits.length >= 7) out += '-' + digits.slice(7, 9);
  if (digits.length >= 9) out += '-' + digits.slice(9, 11);

  this.value = out;
  validate();
});

/* ── Валидация: кнопка активна только когда всё заполнено */
function validate() {
  const nameOk    = nameInput.value.trim().length > 0;
  const phoneOk   = phoneInput.value.replace(/\D/g, '').length === 11;
  const consentOk = consent.checked;
  submitBtn.disabled = !(nameOk && phoneOk && consentOk);
}

nameInput.addEventListener('input', validate);
consent.addEventListener('change', validate);

// Стартовое состояние — кнопка неактивна
submitBtn.disabled = true;

/* ── Отправка через Formspree (без перезагрузки) ────────── */
form.addEventListener('submit', async function (e) {
  e.preventDefault();

  submitBtn.disabled = true;
  submitBtn.textContent = 'Отправляем…';

  try {
    const res = await fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: { Accept: 'application/json' },
    });

    if (res.ok) {
      form.hidden = true;
      successBlock.hidden = false;
      successBlock.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Отправить заявку';
      alert('Что-то пошло не так. Попробуйте ещё раз или позвоните напрямую.');
    }
  } catch {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Отправить заявку';
    alert('Нет соединения. Проверьте интернет и попробуйте снова.');
  }
});

/* ── Карта: активация по клику (не перехватывает скролл) ─── */
const mapOverlay = document.getElementById('map-overlay');
if (mapOverlay) {
  mapOverlay.addEventListener('click', function () {
    mapOverlay.classList.add('is-hidden');
  });
}

/* ── Лайтбокс: увеличение фото по клику ──────────────────── */
(function () {
  const photos = Array.from(document.querySelectorAll('.photo-main, .gallery-photo'));
  if (photos.length === 0) return;

  const lightbox    = document.getElementById('lightbox');
  const lightboxImg = document.getElementById('lightbox-img');
  const btnClose    = document.getElementById('lightbox-close');
  const btnPrev     = document.getElementById('lightbox-prev');
  const btnNext     = document.getElementById('lightbox-next');

  let currentIndex = 0;

  function show(index) {
    currentIndex = index;
    lightboxImg.src = photos[currentIndex].src;
    lightboxImg.alt = photos[currentIndex].alt;
  }

  function open(index) {
    show(index);
    lightbox.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function close() {
    lightbox.hidden = true;
    document.body.style.overflow = '';
  }

  function next() { show((currentIndex + 1) % photos.length); }
  function prev() { show((currentIndex - 1 + photos.length) % photos.length); }

  photos.forEach((photo, index) => {
    photo.addEventListener('click', () => open(index));
  });

  btnClose.addEventListener('click', close);
  btnNext.addEventListener('click', next);
  btnPrev.addEventListener('click', prev);

  // Клик по затемнённому фону закрывает лайтбокс
  lightbox.addEventListener('click', function (e) {
    if (e.target === lightbox) close();
  });

  // Клавиатура: Esc закрывает, стрелки листают
  document.addEventListener('keydown', function (e) {
    if (lightbox.hidden) return;
    if (e.key === 'Escape')    close();
    if (e.key === 'ArrowRight') next();
    if (e.key === 'ArrowLeft')  prev();
  });

  // Свайп на мобильном
  let touchStartX = 0;
  lightbox.addEventListener('touchstart', function (e) {
    touchStartX = e.changedTouches[0].clientX;
  }, { passive: true });

  lightbox.addEventListener('touchend', function (e) {
    const diff = e.changedTouches[0].clientX - touchStartX;
    const SWIPE_THRESHOLD = 40;
    if (diff > SWIPE_THRESHOLD)  prev();
    if (diff < -SWIPE_THRESHOLD) next();
  }, { passive: true });
})();
