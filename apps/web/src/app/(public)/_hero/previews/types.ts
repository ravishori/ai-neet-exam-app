/** Shared props for every capability preview.
 * Kept in its own file so the six previews and the data map can import
 * the same shape without a circular dependency through data.ts.
 */
export type HeroPreviewImage = {
  src: string;
  alt: string;
  priority?: boolean;
};

export type HeroPreviewProps = {
  image?: HeroPreviewImage;
};
