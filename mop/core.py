from eyed3.id3 import GenreMap, Genre

__all__ = ["Genre", "GENRES"]


class Genres(GenreMap):
    _next_gid = GenreMap.GENRE_ID3V1_MAX + 1

    def __init__(self, *args):
        super().__init__(*args)

    def add(self, name) -> Genre:
        if name in self:
            raise ValueError(f"Genre exists: {name}")

        assert self._next_gid not in self
        gid = self._next_gid
        self._next_gid += 1

        self[gid] = name
        self[name.lower()] = gid

        return self.get(gid)


GENRES = Genres()
