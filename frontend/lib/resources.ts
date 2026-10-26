import type { Resource } from './types';

export function resourceLicenseLabel(resource: Resource, question: string): string | null {
  const reuseAction = /\b(download|redistribut\w*|reuse|remix|licens\w*|use (?:it|them|these) in)\b/i;
  const learning = /\b(tutorials?|lessons?|watch|learn|courses?|guides?|updates?)\b/i;
  // Infer intent for older saved cards too; never modify the stored answer/evidence.
  const viewing = resource.usage === 'view' || (learning.test(question) && !reuseAction.test(question)) || (!resource.usage && (
    (!/\b(samples?|loops?|assets?|footage|presets?|stems?)\b/i.test(question) && !reuseAction.test(question) && learning.test(resource.title))));
  if (viewing) return null;
  if (resource.license_verified === true && resource.license && /^https?:\/\//i.test(resource.license_source_url || '')) return /restrict|non.commercial|attribution|no.derivatives|personal use|cc[ -]by/i.test(resource.license) ? `Restrictions apply · ${resource.license}` : `Verified for stated use · ${resource.license}`;
  return 'Check usage terms';
}
