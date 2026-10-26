import type { NextConfig } from 'next';

// Keep isolated browser QA builds away from a running developer's .next files.
const config: NextConfig = {
  distDir: process.env.CREATOR_STUDIO_QA === '1' ? '.next-qa' : '.next',
};
export default config;
