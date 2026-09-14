'use client';

import React, { useState } from 'react';
import { Shield, Trophy, User } from 'lucide-react';

interface FootballBadgeProps {
  url?: string | null;
  name: string;
  size?: number;
  className?: string;
}

export function FootballBadge({
  url,
  name,
  size = 32,
  className = '',
}: FootballBadgeProps) {
  const [error, setError] = useState(false);

  const initials = name
    ? name
        .split(' ')
        .map((w) => w[0])
        .filter(Boolean)
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'FC';

  if (!url || error) {
    return (
      <div
        className={`inline-flex items-center justify-center font-bold text-xs rounded-full shadow-inner border border-surface1/60 bg-surface0 text-text shrink-0 ${className}`}
        style={{ width: size, height: size }}
        title={name}
      >
        <span style={{ fontSize: Math.max(10, Math.floor(size * 0.38)) }}>
          {initials}
        </span>
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={name}
      width={size}
      height={size}
      onError={() => setError(true)}
      loading="lazy"
      className={`object-contain shrink-0 transition-transform duration-200 hover:scale-110 ${className}`}
      style={{ width: size, height: size, maxWidth: size, maxHeight: size }}
    />
  );
}

interface CompetitionBadgeProps {
  code?: string;
  name: string;
  badge_url?: string | null;
  size?: number;
  className?: string;
}

export function CompetitionBadge({
  code,
  name,
  badge_url,
  size = 36,
  className = '',
}: CompetitionBadgeProps) {
  const [error, setError] = useState(false);

  if (!badge_url || error) {
    const isTournament = code === 'UCL' || code === 'WC';
    return (
      <div
        className={`inline-flex items-center justify-center rounded-xl bg-surface0 border border-surface1 shadow-sm text-blue shrink-0 ${className}`}
        style={{ width: size, height: size }}
        title={name}
      >
        {isTournament ? (
          <Trophy size={Math.floor(size * 0.55)} className="text-yellow" />
        ) : (
          <Shield size={Math.floor(size * 0.55)} className="text-sapphire" />
        )}
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={badge_url}
      alt={name}
      width={size}
      height={size}
      onError={() => setError(true)}
      loading="lazy"
      className={`object-contain shrink-0 drop-shadow-md transition-transform duration-200 hover:scale-105 ${className}`}
      style={{ width: size, height: size, maxWidth: size, maxHeight: size }}
    />
  );
}

interface PlayerAvatarProps {
  image_url?: string | null;
  name: string;
  size?: number;
  className?: string;
}

export function PlayerAvatar({
  image_url,
  name,
  size = 48,
  className = '',
}: PlayerAvatarProps) {
  const [error, setError] = useState(false);

  if (!image_url || error) {
    return (
      <div
        className={`inline-flex items-center justify-center rounded-full bg-surface0 border border-surface1/80 text-subtext0 shrink-0 ${className}`}
        style={{ width: size, height: size }}
        title={name}
      >
        <User size={Math.floor(size * 0.5)} />
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={image_url}
      alt={name}
      width={size}
      height={size}
      onError={() => setError(true)}
      loading="lazy"
      className={`rounded-full object-cover border border-surface1/80 shadow-sm shrink-0 transition-transform duration-200 hover:scale-105 ${className}`}
      style={{ width: size, height: size }}
    />
  );
}
