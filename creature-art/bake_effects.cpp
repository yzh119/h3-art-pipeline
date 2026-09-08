/*
 * Offline creature effect baker, part of VCMI engine
 *
 * License: GNU General Public License v2.0 or later
 * Full text of license available in LICENSE in the repository root
 */
// Offline asset tool: links existing SDL3 rendering functions, without changing VCMI.
#include <SDL3/SDL.h>
#include <SDL3_image/SDL_image.h>
#include <algorithm>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace CSDL_Ext
{
SDL_Surface * drawShadow(SDL_Surface * source, bool shear);
SDL_Surface * drawOutline(SDL_Surface * source, const SDL_Color & color, int thickness);
}

using Clock = std::chrono::steady_clock;

SDL_Surface * load(const std::filesystem::path & path)
{
	auto * loaded = IMG_Load(path.c_str());
	if(!loaded)
		throw std::runtime_error("Cannot load " + path.string() + ": " + SDL_GetError());
	auto * result = SDL_ConvertSurface(loaded, SDL_PIXELFORMAT_ARGB8888);
	SDL_DestroySurface(loaded);
	if(!result)
		throw std::runtime_error(SDL_GetError());
	return result;
}

int main(int argc, char ** argv)
{
	try
	{
		if(argc != 3)
			throw std::runtime_error("Usage: bake_effects bake|generated|prebaked|verify MOD");
		const std::string mode = argv[1];
		if(mode != "bake" && mode != "generated" && mode != "prebaked" && mode != "verify")
			throw std::runtime_error("Unknown mode");
		std::vector<std::filesystem::path> bodies;
		for(const auto & entry : std::filesystem::recursive_directory_iterator(argv[2]))
		{
			const auto name = entry.path().filename().string();
			if(entry.path().extension() == ".png" && name.find('-') == std::string::npos)
				bodies.push_back(entry.path());
		}
		std::sort(bodies.begin(), bodies.end());
		const auto start = Clock::now();
		int effects = 0;
		for(const auto & path : bodies)
		{
			auto * body = load(path);
			const auto stem = path.stem().string();
			const bool outline = stem.starts_with("holding_") || stem.starts_with("mouseon_");
			for(int layer = 0; layer < (outline ? 2 : 1); ++layer)
			{
				const auto target = path.parent_path() / (stem + (layer ? "-overlay.png" : "-shadow.png"));
				auto * image = mode == "prebaked" ? load(target) :
					(layer ? CSDL_Ext::drawOutline(body, SDL_Color{255, 255, 255, 255}, 1) : CSDL_Ext::drawShadow(body, true));
				if(!image)
					throw std::runtime_error("Failed to create effect");
				if(mode == "bake" && !IMG_SavePNG(image, target.c_str()))
					throw std::runtime_error(SDL_GetError());
				if(mode == "verify")
				{
					auto * saved = load(target);
					if(saved->w != image->w || saved->h != image->h || saved->format != image->format)
						throw std::runtime_error("Effect format mismatch: " + target.string());
					for(int y = 0; y < image->h; ++y)
					{
						if(std::memcmp(static_cast<char *>(saved->pixels) + y * saved->pitch,
							static_cast<char *>(image->pixels) + y * image->pitch, image->w * 4) != 0)
							throw std::runtime_error("Effect pixel mismatch: " + target.string());
					}
					SDL_DestroySurface(saved);
				}
				SDL_DestroySurface(image);
				++effects;
			}
			SDL_DestroySurface(body);
		}
		const auto milliseconds = std::chrono::duration<double, std::milli>(Clock::now() - start).count();
		std::cout << "{\"mode\":\"" << mode << "\",\"bodyFrames\":" << bodies.size()
			<< ",\"effects\":" << effects << ",\"milliseconds\":" << milliseconds << "}\n";
	}
	catch(const std::exception & error)
	{
		std::cerr << error.what() << '\n';
		return 1;
	}
}
