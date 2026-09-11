document.querySelector('.nav-toggle')?.addEventListener('click',()=>document.querySelector('.public-header nav')?.classList.toggle('open'));
const adminAside=document.querySelector('.admin-shell aside');
const sideToggle=document.querySelector('.side-toggle');
if(adminAside&&sideToggle){const backdrop=document.createElement('button');backdrop.className='sidebar-backdrop';backdrop.type='button';document.querySelector('.admin-shell').prepend(backdrop);const close=()=>{adminAside.classList.remove('open');backdrop.classList.remove('open');document.body.classList.remove('menu-open')};sideToggle.addEventListener('click',()=>{adminAside.classList.toggle('open');backdrop.classList.toggle('open');document.body.classList.toggle('menu-open')});backdrop.addEventListener('click',close);adminAside.querySelectorAll('a').forEach(a=>a.addEventListener('click',close))}
setTimeout(()=>document.querySelectorAll('.notice').forEach(x=>x.remove()),5000);
const minimumStock=document.querySelector('input[name="minimum_stock"]');if(minimumStock){minimumStock.closest('.form-grid')?.insertAdjacentHTML('beforeend','<label>Comprimento da peça (m)<input class="input" name="piece_length" inputmode="decimal" placeholder="Ex.: 3,00"></label><label>Largura da peça (m)<input class="input" name="piece_width" inputmode="decimal" placeholder="Ex.: 1,20"></label><label>Espessura / altura (m)<input class="input" name="piece_height" inputmode="decimal" placeholder="Opcional"></label>')}
document.querySelector('.admin-shell aside nav a[href$="/obras"]')?.insertAdjacentHTML('afterend','<a href="/admin/calculadora"><i class="bi bi-calculator"></i>Calculadora de teto</a>');
const internalCode=document.querySelector('input[name="internal_code"]');if(internalCode){internalCode.value='';internalCode.placeholder='Gerado automaticamente ao salvar';internalCode.readOnly=true;internalCode.classList.add('auto-code')}
const purchaseProduct=document.querySelector('select[name="product_id"]');
const newPurchaseProduct=purchaseProduct?.closest('form')?.querySelector('.new-product-box');
if(purchaseProduct&&newPurchaseProduct){
    const toggleNewProduct=()=>{newPurchaseProduct.hidden=Boolean(purchaseProduct.value)};
    purchaseProduct.addEventListener('change',toggleNewProduct);
    toggleNewProduct();
}
const monetaryFields=['amount','sale_price','unit_price','unit_cost','sale_value','labor_cost','other_cost'];
monetaryFields.forEach(name=>document.querySelectorAll(`input[name="${name}"]`).forEach(input=>{
    if(input.closest('.currency-input'))return;
    const wrapper=document.createElement('span');
    wrapper.className='currency-input';
    const prefix=document.createElement('span');
    prefix.className='currency-prefix';
    prefix.textContent='R$';
    input.parentNode.insertBefore(wrapper,input);
    wrapper.append(prefix,input);
}));
const formatStoredQuantity=value=>{
    const number=Number(value);
    return Number.isFinite(number)?number.toLocaleString('pt-BR',{maximumFractionDigits:3}):value;
};
document.querySelectorAll('select option').forEach(option=>{
    option.textContent=option.textContent.replace(/(\(|disponível\s+|saldo\s+)(-?\d+(?:\.\d+)?)/gi,(text,prefix,value)=>prefix+formatStoredQuantity(value));
});
document.querySelectorAll('.record-card small').forEach(element=>{
    element.textContent=element.textContent.replace(/(—\s+)(-?\d+(?:\.\d+)?)/,(text,prefix,value)=>prefix+formatStoredQuantity(value));
});
document.querySelectorAll('.activity > strong').forEach(element=>{
    element.textContent=element.textContent.replace(/^-?\d+(?:\.\d+)?/,value=>formatStoredQuantity(value));
});
document.querySelectorAll('.alert-row small').forEach(element=>{
    element.textContent=element.textContent.replace(/(Saldo\s+|mínimo\s+)(-?\d+(?:\.\d+)?)/gi,(text,prefix,value)=>prefix+formatStoredQuantity(value));
});

const addFieldHint=(field,text)=>{
    const container=field?.matches?.('label')?field:(field?.closest?.('label')||field?.parentElement);
    if(!container||container.querySelector(':scope > .field-hint'))return;
    const hint=document.createElement('small');hint.className='field-hint';hint.textContent=text;
    container.appendChild(hint);
};
document.querySelectorAll('form [required]').forEach(field=>{
    const label=field.closest('label');
    if(label&&!label.querySelector('.required-mark')){
        const mark=document.createElement('span');mark.className='required-mark';mark.textContent=' obrigatório';
        label.insertBefore(mark,label.querySelector('input,select,textarea,.currency-input'));
    }
});
document.querySelectorAll('.admin-content form').forEach(form=>{
    if(form.querySelector('[required]')&&!form.querySelector('.required-help')){
        const help=document.createElement('p');help.className='required-help';help.textContent='Os campos marcados como obrigatório precisam ser preenchidos.';
        form.insertBefore(help,form.firstChild);
    }
    form.addEventListener('submit',()=>{
        if(!form.checkValidity())return;
        const button=form.querySelector('button[type="submit"],button:not([type]),input[type="submit"]');
        if(button){button.disabled=true;button.dataset.originalText=button.value||button.textContent;if(button.tagName==='INPUT')button.value='Salvando...';else button.textContent='Salvando...';}
    });
});

if(location.pathname.endsWith('/compras')){
    const form=purchaseProduct?.closest('form');
    const title=form?.closest('.panel')?.querySelector('h2');if(title)title.textContent='Registrar compra — siga as etapas';
    const productLabel=purchaseProduct?.closest('label');addFieldHint(productLabel,'Escolha um produto da lista. Se ele ainda não existe, deixe em “Criar novo produto”.');
    const choice=document.createElement('div');choice.className='choice-feedback';productLabel?.appendChild(choice);
    const updateChoice=()=>{
        const option=purchaseProduct.options[purchaseProduct.selectedIndex];
        choice.textContent=purchaseProduct.value?`Produto escolhido: ${option.textContent}`:'Você vai cadastrar um produto novo nesta compra.';
        choice.classList.toggle('success',Boolean(purchaseProduct.value));
    };
    purchaseProduct?.addEventListener('change',updateChoice);if(purchaseProduct)updateChoice();
    const newTitle=newPurchaseProduct?.querySelector('b');if(newTitle)newTitle.textContent='Dados do novo produto';
    addFieldHint(form?.querySelector('[name="quantity"]')?.closest('label'),'Informe quanto entrou no estoque. Ex.: 10 unidades ou 3,5 metros.');
    addFieldHint(form?.querySelector('[name="unit_cost"]')?.closest('label'),'Digite quanto foi pago por uma unidade ou medida, sem digitar R$.');
    const csrf=form?.querySelector('[name="csrf_token"]')?.value||'';
    document.querySelectorAll('.record-card').forEach(card=>{
        const match=card.querySelector('b')?.textContent.match(/Compra #(\d+)/);if(!match)return;
        const id=match[1],actions=document.createElement('div');actions.className='record-actions';
        const edit=document.createElement('a');edit.className='btn small-btn';edit.href=`/admin/compras/${id}/editar`;edit.innerHTML='<i class="bi bi-pencil"></i> Editar';
        const remove=document.createElement('form');remove.method='post';remove.action=`/admin/compras/${id}/remover`;remove.innerHTML=`<input type="hidden" name="csrf_token" value="${csrf}"><button type="submit" class="btn small-btn danger-btn"><i class="bi bi-trash"></i> Remover</button>`;
        remove.addEventListener('submit',event=>{if(!confirm('Remover esta compra? A quantidade será retirada do estoque e a despesa também será removida do financeiro.'))event.preventDefault();});
        actions.append(edit,remove);card.appendChild(actions);
    });
}
if(location.pathname.endsWith('/vendas')){
    const product=document.getElementById('sale-product');
    addFieldHint(product?.closest('label'),'Primeiro escolha o material que será retirado do estoque.');
    const feedback=document.createElement('div');feedback.className='choice-feedback';product?.closest('label')?.appendChild(feedback);
    const update=()=>{feedback.textContent=product?.value?`Selecionado: ${product.options[product.selectedIndex].textContent}`:'Nenhum produto selecionado.';feedback.classList.toggle('success',Boolean(product?.value));};
    product?.addEventListener('change',update);if(product)update();
    addFieldHint(document.querySelector('[name="quantity"]')?.closest('label'),'Use a mesma unidade mostrada no produto selecionado.');
    addFieldHint(document.querySelector('[name="unit_price"]')?.closest('label'),'Valor cobrado por unidade ou medida, sem digitar R$.');
}
if(location.pathname.endsWith('/estoque')){
    const panel=document.querySelector('.admin-content .panel');
    if(panel){const guide=document.createElement('div');guide.className='screen-guide';guide.innerHTML='<b>Como entender esta tela</b><span>A quantidade mostra o saldo disponível. “Estoque baixo” avisa que o produto chegou ao mínimo definido.</span>';panel.prepend(guide);}
    document.querySelectorAll('.table-wrap tbody tr').forEach(row=>{
        const code=row.querySelector('code')?.textContent.trim();if(!code)return;
        const cell=document.createElement('td'),actions=document.createElement('div'),edit=document.createElement('a');actions.className='table-actions';
        edit.className='btn small-btn';edit.href=`/admin/estoque/produto/${encodeURIComponent(code)}/editar`;edit.innerHTML='<i class="bi bi-pencil"></i> Editar produto';
        const remove=document.createElement('form');remove.method='post';remove.action=`/admin/estoque/produto/${encodeURIComponent(code)}/remover`;
        const csrf=document.querySelector('input[name="csrf_token"]')?.value||'';
        remove.innerHTML=`<input type="hidden" name="csrf_token" value="${csrf}"><button type="submit" class="btn small-btn danger-btn"><i class="bi bi-trash"></i> Excluir</button>`;
        remove.addEventListener('submit',event=>{const name=row.querySelector('td:nth-child(2)')?.textContent.trim();if(!confirm(`Excluir definitivamente “${name}”? O saldo, as movimentações e os registros relacionados também serão apagados. Esta ação não poderá ser desfeita.`))event.preventDefault();});
        actions.append(edit,remove);cell.appendChild(actions);row.appendChild(cell);
    });
    const headerRow=document.querySelector('.table-wrap thead tr');if(headerRow){const header=document.createElement('th');header.textContent='Ações';headerRow.appendChild(header);}
    document.querySelectorAll('.table-wrap tbody td:nth-child(5) strong').forEach(element=>{element.textContent=formatStoredQuantity(element.textContent.trim());});
}
if(location.pathname.includes('/compras/')&&location.pathname.endsWith('/editar')){
    addFieldHint(document.querySelector('[name="quantity"]')?.closest('label'),'Se alterar a quantidade, a diferença será somada ou retirada do estoque.');
    addFieldHint(document.querySelector('[name="unit_cost"]')?.closest('label'),'O total da compra e a despesa financeira serão recalculados.');
}
if(location.pathname.includes('/estoque/produto/')&&location.pathname.endsWith('/editar')){
    addFieldHint(document.querySelector('[name="name"]')?.closest('label'),'O código automático será recriado com base neste nome, na categoria e nas medidas.');
    addFieldHint(document.querySelector('[name="minimum_stock"]')?.closest('label'),'Ao chegar nesta quantidade, o sistema mostrará o aviso “Estoque baixo”.');
    addFieldHint(document.querySelector('[name="current_quantity"]')?.closest('label'),'Digite o saldo real: 12 para doze ou 12.000 para doze mil.');
}
if(location.pathname.endsWith('/obras')){
    const csrf=document.querySelector('input[name="csrf_token"]')?.value||'';
    document.querySelectorAll('.record-grid > a.record-card').forEach(card=>{
        const match=card.getAttribute('href')?.match(/\/obras\/(\d+)$/);if(!match)return;
        const status=card.querySelector('span')?.textContent||'';
        if(status.includes('Concluída')){const badge=document.createElement('span');badge.className='badge success completed-badge';badge.innerHTML='<i class="bi bi-check-circle"></i> Concluída';card.appendChild(badge);return;}
        const form=document.createElement('form');form.className='complete-project-form';form.method='post';form.action=`/admin/obras/${match[1]}/concluir`;
        form.innerHTML=`<input type="hidden" name="csrf_token" value="${csrf}"><button type="submit" class="btn complete-btn"><i class="bi bi-check2-circle"></i> Concluir obra</button>`;
        form.addEventListener('click',event=>event.stopPropagation());
        form.addEventListener('submit',event=>{event.stopPropagation();if(!confirm('Marcar esta obra como concluída?'))event.preventDefault();});
        card.appendChild(form);
    });
}
