# Flujo de ventas de escritorio

Las ventas usan exclusivamente la base local y no requieren acceso a Internet.
El servicio web y los reportes remotos no intervienen en el cobro.

## Precios e importes

- Cambiar de cliente o lista A/B recalcula el carrito completo, incluidos descuentos
  y promociones NxM. Un precio B de cero es distinto de un precio B ausente.
- Escáner, búsqueda y accesos táctiles usan el campo de cantidad. Las cantidades
  admiten hasta cuatro decimales y los precios/importes hasta dos. Se rechazan
  NaN, infinitos, valores negativos y números que exceden la capacidad de la BD.
- Cada subtotal se redondea a centavos antes de sumar y aplicar el descuento global,
  igual que en la transacción de venta.
- Antes de abrir el cobro, `SalesController.quote_cart()` revalida los precios desde
  la BD y la disponibilidad acumulada de stock (incluidos ingredientes y paquetes).
  Si el total cambia, el operador debe aceptar el nuevo importe.
- La pantalla envía `expected_total` al guardar. Si los precios/promociones cambian
  durante el cobro, la transacción se revierte sin modificar stock ni caja. Se debe
  volver a abrir el cobro para revisar el importe vigente.
- El código de balanza de 13 dígitos con prefijo `20` contiene PLU e importe. El peso
  se infiere usando el precio A y se redondea a cuatro decimales; después se aplican
  la lista y los descuentos/promociones del ticket. El importe impreso por la balanza
  puede diferir del final cuando hay descuentos o lista B.
- Los importes visuales usan el símbolo y los decimales configurados. El monto
  recibido y el segundo importe se envían como strings decimales, no como floats.

## Cobro y errores

El botón Cobrar requiere un carrito, catálogo cargado y caja activa. Los errores de
lectura no se confunden con un catálogo vacío. Los mensajes de error/advertencia
permanecen visibles hasta la siguiente operación.

El guardado se ejecuta en un worker con una copia del carrito. El hilo de Tk consume
el resultado mediante una cola: el worker no toca widgets. Mientras se guarda, no se
puede iniciar otro cobro ni cerrar su diálogo. Un error conserva el carrito y permite
reintentar. QR y QR Billetera se normalizan como el mismo método; no pueden usarse
para eludir la validación de métodos distintos en un pago mixto.

## Modificación de tickets

Devoluciones navega a Ventas sin anular primero. Ventas verifica todas las líneas,
el cliente, las cantidades y los permisos de venta libre; prepara los precios y
renderiza el carrito completo antes de solicitar la anulación. Si falta un artículo,
falla la preparación o no se puede anular, el ticket original se conserva y no queda
una restauración parcial. Una preparación fallida conserva el contexto para reintentar.

Tras una anulación exitosa se trabaja con los precios vigentes del cliente, no con
un precio antiguo forzado. Se informa al operador que debe revisar descuentos y
total. Abandonar este carrito no deshace automáticamente la anulación confirmada.

## Teclado e interfaz

- F5/F10: cobrar; F6: volver al escáner; F7: venta libre para administrador/gerente.
- Suprimir/Ctrl+Suprimir no eliminan productos cuando se está editando un campo.
  Los atajos de la vista no intervienen en otros modales.
- Búsqueda: selección con flechas y Enter, lista desplazable de altura limitada,
  estados de carga/sin resultados y rechazo de respuestas obsoletas.
- La venta libre inválida conserva el formulario y muestra el error junto a sus
  campos. Los diálogos de edición tienen espacio para nombres largos y errores.
- Las recargas no roban el foco. El stock fraccionario se muestra sin truncarlo.

## Pruebas de regresión

- `tests/controllers/test_sales_checkout.py`: catálogo, precios vigentes, stock,
  redondeo, rollback por cambio de total y pagos inválidos.
- `tests/views/test_sales_view.py`: cantidades, listas/clientes, balanza, búsqueda,
  restauración, estados, atajos y worker de cobro.
- `tests/views/test_sales_view_widgets.py`: construcción real de widgets y diálogos
  con escalas 100%, 125% y 150%, ventanas ocultas y base de prueba aislada.

Las pruebas de widgets no reemplazan una revisión visual manual en el equipo final,
ni pruebas con una balanza, impresora o lector físicos.
