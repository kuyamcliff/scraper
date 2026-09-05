from __future__ import annotations

import asyncio
import json
import click
from rich.console import Console

from .scraper import NyaaScraper, ScrapeConfig

console = Console()


def _resolution(value: str) -> str:
    allowed = {"240p","360p","480p","576p","720p","1080p","1440p","2160p","4k","4320p"}
    value = value.lower()
    if value not in allowed:
        raise click.BadParameter(f"must be one of {sorted(allowed)}")
    return "2160p" if value == "4k" else value


@click.group()
def cli():
    """Production-grade anime release discovery and quality ranking."""


@cli.command()
@click.argument("query")
@click.option("--season", type=int)
@click.option("--episode", type=float)
@click.option("--absolute", "absolute_episode", type=int)
@click.option("--resolution", "min_resolution", default="1080p", callback=lambda ctx, p, v: _resolution(v))
@click.option("--max-resolution", callback=lambda ctx, p, v: _resolution(v) if v else None)
@click.option("--dual-audio", is_flag=True)
@click.option("--sub-only", is_flag=True)
@click.option("--trusted", is_flag=True)
@click.option("--include-related", is_flag=True)
@click.option("--min-seeds", type=click.IntRange(min=0), default=0)
@click.option("--max", "max_results", type=click.IntRange(min=1), default=20)
@click.option("--pages", type=click.IntRange(min=1, max=20), default=3)
@click.option("--profile", type=click.Choice(["streaming","archival","mobile","maximum"]), default="streaming")
@click.option("--policy-file", type=click.Path(exists=True, dir_okay=False))
@click.option("--json-out", is_flag=True)
def search(query, season, episode, absolute_episode, min_resolution, max_resolution, dual_audio, sub_only, trusted,
           include_related, min_seeds, max_results, pages, profile, policy_file, json_out):
    """Search and rank releases for an anime title."""
    cfg = ScrapeConfig(query=query, expected_season=season, expected_episode=episode, expected_absolute=absolute_episode,
                       min_resolution=min_resolution, max_resolution=max_resolution, dual_audio=dual_audio, sub_only=sub_only,
                       trusted_only=trusted, include_related=include_related, min_seeders=min_seeds, max_results=max_results,
                       max_pages=pages, profile=profile, policy_file=policy_file)
    asyncio.run(_run(cfg, json_out))


@cli.command(name="id")
@click.argument("anilist_id", type=int)
@click.option("--season", type=int)
@click.option("--episode", type=float)
@click.option("--absolute", "absolute_episode", type=int)
@click.option("--resolution", default="1080p", callback=lambda ctx, p, v: _resolution(v))
@click.option("--max-resolution", callback=lambda ctx, p, v: _resolution(v) if v else None)
@click.option("--dual-audio", is_flag=True)
@click.option("--sub-only", is_flag=True)
@click.option("--trusted", is_flag=True)
@click.option("--min-seeds", type=click.IntRange(min=0), default=0)
@click.option("--max", "max_results", type=click.IntRange(min=1), default=20)
@click.option("--profile", type=click.Choice(["streaming","archival","mobile","maximum"]), default="streaming")
@click.option("--json-out", is_flag=True)
def search_id(anilist_id, season, episode, absolute_episode, resolution, max_resolution, dual_audio, sub_only, trusted, min_seeds, max_results, profile, json_out):
    cfg = ScrapeConfig(anilist_id=anilist_id, expected_season=season, expected_episode=episode, expected_absolute=absolute_episode,
                       min_resolution=resolution, max_resolution=max_resolution, dual_audio=dual_audio, sub_only=sub_only,
                       trusted_only=trusted, min_seeders=min_seeds, max_results=max_results, profile=profile)
    asyncio.run(_run(cfg, json_out))


async def _run(cfg: ScrapeConfig, json_out: bool):
    scraper = NyaaScraper(cfg)
    try:
        result = await scraper.run()
        if json_out:
            print(json.dumps([r.to_dict() for r in result], ensure_ascii=False, indent=2))
        else:
            scraper.print_results(result)
    finally:
        await scraper.close()


if __name__ == "__main__":
    cli()
