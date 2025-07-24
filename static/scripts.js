document.addEventListener('DOMContentLoaded', () => {
  const cart = {};
  const cartItemsContainer = document.getElementById('cart-items');
  const itemsCountElement = document.getElementById('items-count');
  const subtotalElement = document.getElementById('subtotal');
  const totalElement = document.getElementById('total');
  const deliveryFee = 50;

  // Add to Cart / Remove Button Click Handler
  document.querySelectorAll('.add-to-cart').forEach(button => {
    button.addEventListener('click', () => {
      const itemName = button.dataset.item;
      const itemPrice = parseFloat(button.dataset.price);
      const quantityInput = document.querySelector(`input[name="${itemName}"]`);

      if (!quantityInput) return console.error(`No quantity input for ${itemName}`);

      let quantity = parseInt(quantityInput.value, 10) || 0;
      
      // Toggle between add and remove
      if (button.textContent.trim() === 'Add') {
        quantity = quantity + 1;
        button.textContent = 'Remove';
      } else {
        quantity = 0;
        button.textContent = 'Add';
      }
      
      quantityInput.value = quantity;

      if (quantity > 0) {
        cart[itemName] = { name: itemName, price: itemPrice, quantity };
      } else {
        delete cart[itemName];
      }
      updateCartDisplay();
    });
  });

  // Manual Quantity Input Listener
  document.querySelectorAll('input[type="number"]').forEach(input => {
    input.addEventListener('input', () => {
      const itemName = input.name;
      const button = document.querySelector(`.add-to-cart[data-item="${itemName}"]`);
      const itemPrice = parseFloat(button?.dataset.price || 0);
      const quantity = parseInt(input.value, 10) || 0;

      if (button) {
        button.textContent = quantity > 0 ? 'Remove' : 'Add';
      }
      
      if (quantity > 0) {
        cart[itemName] = { name: itemName, price: itemPrice, quantity };
      } else {
        delete cart[itemName];
      }
      updateCartDisplay();
    });
  });

  function updateCartDisplay() {
    cartItemsContainer.innerHTML = '';
    let totalItems = 0;
    let subtotal = 0;

    Object.values(cart).forEach(item => {
      totalItems += item.quantity;
      const itemTotal = item.price * item.quantity;
      subtotal += itemTotal;

      const itemDiv = document.createElement('div');
      itemDiv.className = 'cart-item';
      itemDiv.innerHTML = `
        <span class="cart-item-name">${item.name}</span>
        <span class="cart-item-qty">x${item.quantity}</span>
        <span class="cart-item-price">Nrs ${itemTotal.toFixed(2)}</span>
      `;
      cartItemsContainer.appendChild(itemDiv);
    });

    itemsCountElement.textContent = totalItems;
    subtotalElement.textContent = `Nrs ${subtotal.toFixed(2)}`;
    totalElement.textContent = `Nrs ${(subtotal + deliveryFee).toFixed(2)}`;
  }

  const form = document.querySelector('form.shopping-form, form#menu-form');
  if (form) {
    form.addEventListener('submit', e => {
      if (Object.keys(cart).length === 0) {
        e.preventDefault();
        alert('Please add at least one item to your order before submitting.');
        return;
      }

      let hiddenInput = form.querySelector('input[name="items"]');
      if (!hiddenInput) {
        hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = 'items';
        form.appendChild(hiddenInput);
      }
      hiddenInput.value = JSON.stringify(cart);
    });
  }
});

// Mobile Menu Functionality
document.addEventListener('DOMContentLoaded', function() {
  // Mobile menu elements
  const overlay = document.querySelector('.overlay');
  const mobileMenu = document.querySelector('.mobile-menu');
  const mobileMenuToggles = document.querySelectorAll('.mobile-menu-toggle');
  
  // Toggle mobile menu
  mobileMenuToggles.forEach(toggle => {
    toggle.addEventListener('click', function() {
      mobileMenu.classList.toggle('active');
      overlay.classList.toggle('active');
      
      // Prevent scrolling when menu is open
      document.body.style.overflow = mobileMenu.classList.contains('active') ? 'hidden' : '';
    });
  });
  
  // Close menu when clicking overlay
  overlay.addEventListener('click', function() {
    mobileMenu.classList.remove('active');
    overlay.classList.remove('active');
    document.body.style.overflow = '';
  });
  
  // Close menu when clicking a link (optional)
  const mobileNavLinks = document.querySelectorAll('.mobile-nav-link');
  mobileNavLinks.forEach(link => {
    link.addEventListener('click', function() {
      mobileMenu.classList.remove('active');
      overlay.classList.remove('active');
      document.body.style.overflow = '';
    });
  });
});