document.addEventListener('DOMContentLoaded', function() {
  // ACCORDION
  document.querySelectorAll('.accordion .toggle-btn').forEach(btn => {
    btn.addEventListener('click', function() {
      const accordion = this.closest('.accordion');
      accordion.classList.toggle('open');
    });
  });

  // SAVE BUTTON
  document.querySelectorAll('.btn-save').forEach(saveBtn => {
    saveBtn.addEventListener('click', function() {
      const card = this.closest('.card');
      card.classList.add('highlighted');
      this.style.display = 'none';
      const cancelBtn = card.querySelector('.btn-cancel');
      if (cancelBtn) cancelBtn.style.display = 'inline-block';

      // Optional: send AJAX to server to remember favorite
      // fetch('/api/favorite', { method: 'POST', body: JSON.stringify({ tender: this.dataset.tender }) })
    });
  });

  // CANCEL BUTTON
  document.querySelectorAll('.btn-cancel').forEach(cancelBtn => {
    cancelBtn.addEventListener('click', function() {
      const card = this.closest('.card');
      card.classList.remove('highlighted');
      this.style.display = 'none';
      const saveBtn = card.querySelector('.btn-save');
      if (saveBtn) saveBtn.style.display = 'inline-block';

      // Optional: send AJAX to server to remove favorite
      // fetch('/api/favorite', { method: 'DELETE', body: JSON.stringify({ tender: this.dataset.tender }) })
    });
  });
});