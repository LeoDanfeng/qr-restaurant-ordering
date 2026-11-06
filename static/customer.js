const $ = s => document.querySelector(s);
const params = new URLSearchParams(location.search);
let tableId = Number(params.get("table")) || 0, menuData = {items:[],categories:[]}, cart = {};
const yen = n => "¥" + (n/100).toLocaleString("ja-JP");
async function api(url, opts={}) { const r=await fetch(url,{headers:{"Content-Type":"application/json"},...opts}); const d=await r.json(); if(!r.ok) throw Error(d.error||"Request failed"); return d; }
function escapeHtml(s){return String(s||"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function renderMenu() {
  $("#tableBadge").textContent = tableId ? `Ordering for table ${tableId}` : "Choose a table to get started";
  $("#categoryTabs").innerHTML = `<button class="cat-tab active" data-cat="all">All</button>` + menuData.categories.map(c=>`<button class="cat-tab" data-cat="${c.id}">${escapeHtml(c.name)}</button>`).join("");
  drawItems("all");
  document.querySelectorAll(".cat-tab").forEach(b=>b.onclick=()=>{document.querySelectorAll(".cat-tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");drawItems(b.dataset.cat)});
}
function drawItems(cat) {
  const items=menuData.items.filter(x=>cat==="all"||String(x.category_id)===String(cat));
  $("#menu").innerHTML=items.map(x=>`<article class="food-card"><div class="food-placeholder">${(x.name||"F").slice(0,1).toUpperCase()}</div><div class="food-info"><div><span class="food-category">${escapeHtml(x.category_name||"MENU")}</span><h3>${escapeHtml(x.name)}</h3><p>${escapeHtml(x.description)}</p></div><div class="food-bottom"><b>${yen(x.price_cents)}</b><button class="add-btn" data-id="${x.id}" aria-label="Add ${escapeHtml(x.name)}">+</button></div></div></article>`).join("") || `<p class="muted">No items in this category yet.</p>`;
  document.querySelectorAll(".add-btn").forEach(b=>b.onclick=()=>{const id=Number(b.dataset.id);cart[id]=(cart[id]||0)+1;updateCartFab();b.textContent="✓";setTimeout(()=>b.textContent="+",650)});
}
function updateCartFab(){const count=Object.values(cart).reduce((a,b)=>a+b,0);$("#cartFab").hidden=count===0;$("#cartCount").textContent=count}
function drawCart(){const items=menuData.items.filter(x=>cart[x.id]);$("#cartLines").innerHTML=items.map(x=>`<div class="cart-line"><div class="cart-line-main"><b>${escapeHtml(x.name)}</b><small>${yen(x.price_cents)} each</small></div><div class="qty"><button data-id="${x.id}" data-delta="-1">−</button><b>${cart[x.id]}</b><button data-id="${x.id}" data-delta="1">+</button></div><strong>${yen(x.price_cents*cart[x.id])}</strong></div>`).join("");
  document.querySelectorAll(".qty button").forEach(b=>b.onclick=()=>{let id=Number(b.dataset.id);cart[id]+=Number(b.dataset.delta);if(cart[id]<=0)delete cart[id];drawCart();updateCartFab()});
  $("#cartTotal").textContent=yen(items.reduce((s,x)=>s+x.price_cents*cart[x.id],0));
}
$("#cartFab").onclick=()=>{$("#cartOverlay").hidden=false;drawCart()};
$("#closeCart").onclick=()=>$("#cartOverlay").hidden=true;
$("#doneBtn").onclick=()=>{$("#successOverlay").hidden=true;cart={};updateCartFab()};
$("#submitOrder").onclick=async()=>{if(!tableId){$("#cartMessage").textContent="Open this page using the QR code assigned to your table.";return}
  const btn=$("#submitOrder");btn.disabled=true;btn.textContent="Sending…";$("#cartMessage").textContent="";
  try{const result=await api("/api/orders",{method:"POST",body:JSON.stringify({table_id:tableId,note:$("#orderNote").value,items:Object.entries(cart).map(([item_id,quantity])=>({item_id:Number(item_id),quantity}))})});
  $("#cartOverlay").hidden=true;$("#successText").textContent=`Order #${result.order_id} has been sent to the restaurant.`;$("#successOverlay").hidden=false;$("#orderNote").value="";
  }catch(e){$("#cartMessage").textContent=e.message}finally{btn.disabled=false;btn.textContent="Place order"}
};
api("/api/menu").then(d=>{menuData=d;renderMenu()}).catch(e=>{$("#menu").textContent=e.message});
