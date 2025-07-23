document.addEventListener('DOMContentLoaded', () => {
  const cart = {};
  const cartItemsContainer = document.getElementById('cart-items');
  const itemsCountElement = document.getElementById('items-count');
  const subtotalElement = document.getElementById('subtotal');
  const totalElement = document.getElementById('total');
  const deliveryFee = 50;

  // Handle Add/Remove button clicks for all buttons with class "add-to-cart"
  document.querySelectorAll('.add-to-cart').forEach(button => {
    button.addEventListener('click', () => {
      const itemName = button.getAttribute('data-item');
      const itemPrice = parseFloat(button.getAttribute('data-price'));

      // Find the quantity input corresponding to this item by name attribute
      const quantityInput = document.querySelector(`input[name="${itemName}"]`);
      if (!quantityInput) {
        console.error(`Quantity input not found for item: ${itemName}`);
        return;
      }

      // Increment quantity by 1 on button click, or remove if already present
      let quantity = parseInt(quantityInput.value, 10) || 0;

      if (quantity === 0) {
        quantity = 1;
      } else {
        quantity += 1;
      }
      quantityInput.value = quantity;

      button.textContent = quantity > 0 ? 'Remove' : 'Add';

      // Update cart data structure accordingly
      if (quantity > 0) {
        cart[itemName] = { name: itemName, price: itemPrice, quantity };
      } else {
        delete cart[itemName];
      }

      updateCartDisplay();
    });
  
    // Listen for manual changes in quantity input fields
    document.querySelectorAll('input[type="number"]').forEach(input => {
      input.addEventListener('input', (e) => {
        const itemName = input.name;
        const button = document.querySelector(`.add-to-cart[data-item="${itemName}"]`);
        const itemPrice = parseFloat(button.getAttribute('data-price'));
        let quantity = parseInt(input.value, 10) || 0;
  
        if (quantity > 0) {
          cart[itemName] = { name: itemName, price: itemPrice, quantity };
          if (button) button.textContent = 'Remove';
        } else {
          delete cart[itemName];
          if (button) button.textContent = 'Add';
        }
        updateCartDisplay();
      });
    });
  });

  // Update the cart summary panel
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

  // On form submit, add the cart data as a hidden input (JSON string) for backend processing
  const form = document.querySelector('form.shopping-form, form#menu-form'); // matches both pages
  if (form) {
    form.addEventListener('submit', e => {
      if (Object.keys(cart).length === 0) {
        e.preventDefault();
        alert('Please add at least one item to your order before submitting.');
        return;
      }
      // Add or update hidden input with JSON string of cart items
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
