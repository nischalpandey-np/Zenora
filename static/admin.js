document.addEventListener('DOMContentLoaded', function() {
  // Mobile Menu Toggle
  const mobileMenuToggle = document.getElementById('mobileMenuToggle');
  const adminSidebar = document.getElementById('adminSidebar');
  
  mobileMenuToggle.addEventListener('click', function() {
    adminSidebar.classList.toggle('active');
  });

  // Tabs Functionality
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  
  tabBtns.forEach(btn => {
    btn.addEventListener('click', function() {
      const tabId = this.getAttribute('data-tab');
      
      // Update active tab button
      tabBtns.forEach(b => b.classList.remove('active'));
      this.classList.add('active');
      
      // Show corresponding tab content
      tabContents.forEach(content => {
        content.classList.remove('active');
        if (content.id === `${tabId}-tab`) {
          content.classList.add('active');
        }
      });
    });
  });

  // Status Filter
  const statusBtns = document.querySelectorAll('.status-btn');
  const orderRows = document.querySelectorAll('tbody tr[data-status]');
  
  statusBtns.forEach(btn => {
    btn.addEventListener('click', function() {
      const status = this.getAttribute('data-status');
      
      // Update active status button
      statusBtns.forEach(b => b.classList.remove('active'));
      this.classList.add('active');
      
      // Filter order rows
      orderRows.forEach(row => {
        if (status === 'all' || row.getAttribute('data-status') === status) {
          row.style.display = '';
        } else {
          row.style.display = 'none';
        }
      });
    });
  });

  // Modal Handling
  const modals = {
    approve: document.getElementById('approveModal'),
    decline: document.getElementById('declineModal')
  };
  
  // Approve Order Buttons
  document.querySelectorAll('.btn-approve').forEach(btn => {
    btn.addEventListener('click', function() {
      const orderId = this.getAttribute('data-order-id');
      document.getElementById('approveOrderId').value = orderId;
      modals.approve.classList.add('active');
    });
  });
  
  // Decline Order Buttons
  document.querySelectorAll('.btn-decline').forEach(btn => {
    btn.addEventListener('click', function() {
      const orderId = this.getAttribute('data-order-id');
      document.getElementById('declineOrderId').value = orderId;
      modals.decline.classList.add('active');
    });
  });
  
  // Close Modals
  document.querySelectorAll('.btn-modal-close, .btn-modal-cancel').forEach(btn => {
    btn.addEventListener('click', function() {
      Object.values(modals).forEach(modal => {
        modal.classList.remove('active');
      });
    });
  });
  
  // Close modal when clicking outside
  window.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) {
      e.target.classList.remove('active');
    }
  });

  // Form Submissions
  document.getElementById('approveForm').addEventListener('submit', function(e) {
    e.preventDefault();
    submitOrderUpdate(this);
  });
  
  document.getElementById('declineForm').addEventListener('submit', function(e) {
    e.preventDefault();
    if (!this.decline_reason.value.trim()) {
      showToast('Please provide a decline reason', 'error');
      return;
    }
    submitOrderUpdate(this);
  });

  // Submenu Toggle
  document.querySelectorAll('.has-submenu').forEach(item => {
    item.addEventListener('click', function(e) {
      if (e.target.classList.contains('submenu-toggle') || e.target.parentElement.classList.contains('submenu-toggle')) {
        return;
      }
      
      e.preventDefault();
      const submenu = this.querySelector('.submenu');
      const toggle = this.querySelector('.submenu-toggle');
      
      submenu.classList.toggle('active');
      toggle.classList.toggle('fa-chevron-down');
      toggle.classList.toggle('fa-chevron-up');
    });
  });

  // Initialize date filters
  const today = new Date();
  const oneWeekAgo = new Date();
  oneWeekAgo.setDate(today.getDate() - 7);
  
  document.getElementById('dateFrom').valueAsDate = oneWeekAgo;
  document.getElementById('dateTo').valueAsDate = today;
});

// Submit Order Update
function submitOrderUpdate(form) {
  const formData = new FormData(form);
  const submitBtn = form.querySelector('button[type="submit"]');
  const originalText = submitBtn.innerHTML;
  
  // Show loading state
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
  
  fetch(form.action, {
    method: 'POST',
    body: JSON.stringify(Object.fromEntries(formData)),
    headers: {
      'Content-Type': 'application/json'
    }
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showToast(data.message || 'Order updated successfully!', 'success');
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } else {
      showToast(data.message || 'Error updating order', 'error');
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalText;
    }
  })
  .catch(error => {
    console.error('Error:', error);
    showToast('An error occurred', 'error');
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalText;
  });
}

// Show Toast Notification
function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = 'toast show ' + type;
  
  setTimeout(() => {
    toast.className = 'toast';
  }, 3000);
}