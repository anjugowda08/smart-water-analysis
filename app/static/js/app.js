document.addEventListener('DOMContentLoaded', () => {
  const fileInput = document.getElementById('csvFile');
  const fileName = document.getElementById('fileName');
  if (fileInput && fileName) {
    fileInput.addEventListener('change', () => {
      fileName.textContent = fileInput.files.length ? fileInput.files[0].name : 'Choose CSV file';
    });
  }
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', () => {
      const submit = form.querySelector('button[type="submit"],button:not([type])');
      if (submit && !form.hasAttribute('data-no-loading')) {
        submit.dataset.originalText = submit.innerText;
        submit.disabled = true;
        submit.innerText = 'Please wait…';
      }
    });
  });
});
