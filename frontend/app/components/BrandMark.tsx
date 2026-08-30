// Знак бренда — картинка из public/, а не иконка lucide: у логотипа
// собственные цвета, они не должны зависеть от CSS конкретной страницы.
// Проп size повторяет API иконок lucide, чтобы места использования
// (<BrandMark size={28} />) остались без изменений.
export function BrandMark({ size = 24 }: { size?: number }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- логотип фиксированного
    // размера из public/: next/image не даёт здесь ни оптимизации, ни ленивой загрузки
    <img src="/brand-mark.svg" alt="" width={size} height={size} />
  );
}
