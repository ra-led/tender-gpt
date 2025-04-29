document.addEventListener('DOMContentLoaded', function(){
  // collapse your old binder into reusable functions
  function bindAccordion(root){
    root.querySelectorAll('.accordion .toggle-btn').forEach(btn => {
      // ensure we don't double-bind
      if (btn._bound) return;
      btn._bound = true;
      btn.addEventListener('click', function(){
        this.closest('.accordion').classList.toggle('open');
      });
    });
  }

  function bindSaveCancel(root){
    // SAVE
    root.querySelectorAll('.btn-save').forEach(btn => {
      if (btn._bound) return;
      btn._bound = true;
      btn.addEventListener('click', function(){
        const card = this.closest('.card');
        card.classList.add('highlighted');
        this.style.display = 'none';
        const cancelBtn = card.querySelector('.btn-cancel');
        if (cancelBtn) cancelBtn.style.display = 'inline-block';
      });
    });
    // CANCEL
    root.querySelectorAll('.btn-cancel').forEach(btn => {
      if (btn._bound) return;
      btn._bound = true;
      btn.addEventListener('click', function(){
        const card = this.closest('.card');
        card.classList.remove('highlighted');
        this.style.display = 'none';
        const saveBtn = card.querySelector('.btn-save');
        if (saveBtn) saveBtn.style.display = 'inline-block';
      });
    });
  }

  // initial bind on page load
  bindAccordion(document);
  bindSaveCancel(document);

  // infinite scroll
  let loading = false;
  window.addEventListener('scroll', throttle(onScroll, 200));

  function onScroll(){
    if (loading) return;
    if (!window.PAGINATION.hasNext) return;

    const scrolledToBottom = window.innerHeight + window.pageYOffset 
                              >= document.body.offsetHeight - 100;
    if (scrolledToBottom){
      loadNextPage();
    }
  }

  function loadNextPage(){
    loading = true;
    window.PAGINATION.page += 1;

    const { clientId, startDate, endDate, page } = window.PAGINATION;
    const url = `/dashboard/${clientId}/data`
            + `?page=${page}`
            + `&start_date=${startDate}`
            + `&end_date=${endDate}`;

    fetch(url)
      .then(r => r.json())
      .then(data => {
        const container = document.getElementById('tender-container');
        container.insertAdjacentHTML('beforeend', data.html);

        // re-bind events on the newly added markup
        bindAccordion(container);
        bindSaveCancel(container);

        window.PAGINATION.hasNext = data.has_next;

        if (!data.has_next){
          document.getElementById('no-more-data').style.display = 'block';
        }
      })
      .catch(console.error)
      .finally(() => {
        loading = false;
      });
  }

  // simple throttle helper
  function throttle(fn, wait){
    let last = 0;
    return function(){
      const now = Date.now();
      if (now - last > wait){
        fn();
        last = now;
      }
    }
  }
});