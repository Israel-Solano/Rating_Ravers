(async () => {

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

function clean(str = "") {
    return str
        .replace(/\u00a0/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}

function text(el) {
    if (!el) return "";
    return clean(el.innerText || el.textContent || "");
}

////////////////////////////////////////////////////////////
// RENT INFO
////////////////////////////////////////////////////////////

function findLabel(label) {
    const labels = $$(".rentInfoLabel");
    const item = labels.find(l => text(l).toLowerCase() === label.toLowerCase());
    if (!item) return "";
    return text(item.parentElement.querySelector(".rentInfoDetail"));
}

////////////////////////////////////////////////////////////
// GENERIC SECTION SEARCH (OLD LAYOUT) — FIXED
////////////////////////////////////////////////////////////

function findSection(title, { maxNodes = 8, maxChars = 1200 } = {}) {

    const headings = $$("h2,h3,h4,.section-heading");
    const norm = s => s.toLowerCase().trim();

    let heading = headings.find(h => norm(text(h)) === norm(title));

    if (!heading) {
        heading = headings.find(h => {
            const t = text(h).toLowerCase();
            return t.includes(title.toLowerCase()) && t.length < title.length + 15;
        });
    }

    if (!heading) return "";

    const values = [];
    let node = heading.nextElementSibling;
    let nodeCount = 0;
    let charCount = 0;

    while (node && nodeCount < maxNodes && charCount < maxChars) {

        if (/^H[1-6]$/.test(node.tagName) || node.classList.contains("section-heading")) break;

        node.querySelectorAll?.("li").forEach(li => {
            const t = text(li);
            if (t) {
                values.push(t);
                charCount += t.length;
            }
        });

        if (!node.querySelector("li")) {
            const t = text(node);
            if (t.length && t.length < 300) {
                values.push(t);
                charCount += t.length;
            }
        }

        node = node.nextElementSibling;
        nodeCount++;
    }

    return [...new Set(values)].join(" | ");
}

////////////////////////////////////////////////////////////
// NEW FEES & POLICIES LAYOUT
////////////////////////////////////////////////////////////

function extractFeesPanel(selector) {
    const panel = $(selector);
    if (!panel) return "";

    const groups = [];

    panel.querySelectorAll(".level1 > li").forEach(group => {
        const title = text(group.querySelector(".header-column span"));
        const parts = [];

        group.querySelectorAll(".level2 > li").forEach(li => {
            const fee = text(li.querySelector(".feeName"));
            const value = text(li.querySelector(".feeValue"));
            if (fee || value) parts.push(`${fee}: ${value}`);
        });

        const restrictions = text(group.querySelector(".commentsWrapper"));
        if (restrictions) parts.push(restrictions);

        groups.push(title ? `${title} - ${parts.join(", ")}` : parts.join(", "));
    });

    return groups.join(" | ");
}

function extractUtilities() {
    const card = [...document.querySelectorAll(".feesPoliciesCard")]
        .find(c => text(c.querySelector("h3")).toLowerCase().includes("utilities"));
    if (!card) return "";
    return [...card.querySelectorAll("li")].map(text).filter(Boolean).join(" | ");
}

function extractLeaseOptions() {
    const card = [...document.querySelectorAll(".feesPoliciesCard")]
        .find(c => text(c.querySelector("h3")).toLowerCase().includes("lease"));
    if (!card) return "";
    return [...card.querySelectorAll("li")].map(text).filter(Boolean).join(" | ");
}

////////////////////////////////////////////////////////////
// UNIT GRID — price/sqft parsing (DOM-based fallback)
////////////////////////////////////////////////////////////

function extractUnits(schemaSqft = {}) {
    return $$(".js-unitContainerV3").map(li => {

        let price = parseFloat(li.dataset.maxrent || "") || null;
        if (!price) {
            const priceText = text(li.querySelector(".pricingColumn span"));
            price = parseFloat(priceText.replace(/[^0-9.]/g, "")) || null;
        }

        const sqftText = text(
            [...li.querySelectorAll(".sqftColumn span")]
                .find(s => !s.classList.contains("screenReaderOnly"))
        );
        let sqft = parseFloat(sqftText.replace(/,/g, "")) || null;

        const unitNumber = li.dataset.unit || "";

        // FIX: the sqft column selector often doesn't match on newer page
        // layouts, leaving sqft null even though the JSON-LD schema data has
        // it (keyed by unit number, e.g. "3309"). Backfill from there before
        // giving up, exactly like extractUnitsFromData() already does.
        if (!sqft && unitNumber && schemaSqft[unitNumber]) {
            sqft = schemaSqft[unitNumber];
        }

        const available = text(li.querySelector(".dateAvailable"))
            .replace(/availibility/i, "")
            .trim();

        // Check if unit is available (not "Not Available")
        const isAvailable = available && 
            !available.toLowerCase().includes("not available") && 
            !available.toLowerCase().includes("unavailable");

        return {
            unit: unitNumber,
            beds: li.dataset.beds || "",
            baths: li.dataset.baths || "",
            price,
            sqft,
            available,
            isAvailable,
            hasSqft: sqft !== null && sqft > 0,
            sqftRange: sqft ? `${sqft.toLocaleString()}` : "N/A"
        };
    }).filter(u => u.price && parseFloat(u.beds) >= 3 && u.price <= 3500);
}

////////////////////////////////////////////////////////////
// FLOORPLAN MODEL CARDS — DOM-based fallback
////////////////////////////////////////////////////////////

function extractFloorplanModels() {
    return $$(".priceBedRangeInfo").map(el => {

        const modelName = text(el.querySelector(".modelName"));

        const rentNums = (text(el.querySelector(".rentLabel")).match(/[\d,]+/g) || [])
            .map(n => parseFloat(n.replace(/,/g, "")));
        if (!rentNums.length) return null;
        const priceLow = Math.min(...rentNums);
        const priceHigh = Math.max(...rentNums);

        const detailSpans = $$(".detailsTextWrapper > span", el).map(text);
        
        // FIX: Extract numbers from text strings
        const bedsText = detailSpans.find(t => /bed/i.test(t)) || "";
        const bedsMatch = bedsText.match(/(\d+\.?\d*)/);
        const beds = bedsMatch ? parseFloat(bedsMatch[1]) : null;

        const bathsText = detailSpans.find(t => /bath/i.test(t)) || "";
        const bathsMatch = bathsText.match(/(\d+\.?\d*)/);
        const baths = bathsMatch ? parseFloat(bathsMatch[1]) : null;

        const sqftText = detailSpans.find(t => /sq\s*ft/i.test(t)) || "";
        const sqftNums = (sqftText.match(/[\d,]+/g) || [])
            .map(n => parseFloat(n.replace(/,/g, "")));
        const sqftLow = sqftNums.length ? Math.min(...sqftNums) : null;
        const sqftHigh = sqftNums.length ? Math.max(...sqftNums) : null;

        const availableText = text(el.querySelector(".availabilityInfo"));
        const isAvailable = availableText && 
            !availableText.toLowerCase().includes("not available") && 
            !availableText.toLowerCase().includes("unavailable");

        return {
            unit: modelName,
            beds,
            baths,
            price: priceLow,
            sqft: sqftLow,
            priceRange: priceLow === priceHigh ? `$${priceLow.toLocaleString()}` : `$${priceLow.toLocaleString()}–$${priceHigh.toLocaleString()}`,
            sqftRange: sqftLow && sqftHigh ? (sqftLow === sqftHigh ? `${sqftLow.toLocaleString()}` : `${sqftLow.toLocaleString()}–${sqftHigh.toLocaleString()}`) : "N/A",
            available: availableText,
            isAvailable: isAvailable,
            isRange: true,
            hasSqft: sqftLow !== null
        };
    }).filter(u => u && u.price && u.beds >= 3 && u.price <= 3500);
}

////////////////////////////////////////////////////////////
// SCHEMA.ORG DATA EXTRACTOR (for sqft when rentals data is missing it)
////////////////////////////////////////////////////////////

function extractSchemaSqft() {
    const scripts = $$('script[type="application/ld+json"]');
    const sqftMap = {};
    
    for (let script of scripts) {
        try {
            const data = JSON.parse(script.textContent);
            
            // Look for containsPlace array which has unit names and sqft
            if (data.containsPlace && Array.isArray(data.containsPlace)) {
                for (let place of data.containsPlace) {
                    const name = place.name || '';
                    const floorPlan = place.accommodationFloorPlan || {};
                    const floorSize = floorPlan.floorSize || {};
                    const sqft = floorSize.value;
                    
                    if (name && sqft) {
                        // Store sqft by the full name
                        sqftMap[name] = parseFloat(sqft);
                        
                        // Also store by the short code (e.g., "Farnsworth Townhome-H7" -> "H7")
                        const shortMatch = name.match(/-([A-Z0-9]+)$/);
                        if (shortMatch) {
                            sqftMap[shortMatch[1]] = parseFloat(sqft);
                        }
                        
                        // Store by the model name without the suffix
                        const baseName = name.replace(/-\w+$/, '').trim();
                        if (baseName && !sqftMap[baseName]) {
                            sqftMap[baseName] = parseFloat(sqft);
                        }
                    }
                }
            }
            
            // Also look for floorPlan information at the main level
            if (data.accommodationFloorPlan) {
                const floorPlan = data.accommodationFloorPlan;
                const floorSize = floorPlan.floorSize || {};
                const sqft = floorSize.value;
                const name = data.name || '';
                if (name && sqft) {
                    sqftMap[name] = parseFloat(sqft);
                }
            }
        } catch (e) {
            // Skip invalid JSON
        }
    }
    
    return sqftMap;
}
////////////////////////////////////////////////////////////
// RENTALS DATA EXTRACTOR (PRIMARY METHOD) - IMPROVED VERSION
////////////////////////////////////////////////////////////

function extractUnitsFromData() {
    const scripts = $$('script');
    let rentalsData = [];
    let rawRentalsString = null;
    
    // Strategy 1: Try to find the rentals array using multiple regex patterns
    for (let script of scripts) {
        const content = script.textContent;
        
        // Try different patterns to find the rentals array
        const patterns = [
            /"rentals"\s*:\s*(\[[\s\S]*?\])/g,
            /"rentals"\s*:\s*(\[[\s\S]*?\])\s*,/g,
            /"rentals"\s*:\s*(\[[\s\S]*?\])\s*}/g,
            /rentals:\s*(\[[\s\S]*?\])/g,
        ];
        
        for (let pattern of patterns) {
            let match;
            while ((match = pattern.exec(content)) !== null) {
                try {
                    let jsonStr = match[1];
                    jsonStr = jsonStr.replace(/,\s*}/g, '}');
                    jsonStr = jsonStr.replace(/,\s*\]/g, ']');
                    jsonStr = jsonStr.replace(/,\s*([\]}])/g, '$1');
                    
                    const parsed = JSON.parse(jsonStr);
                    if (parsed && Array.isArray(parsed) && parsed.length > 0) {
                        if (parsed.some(item => item.Rent !== undefined)) {
                            rentalsData = parsed;
                            rawRentalsString = jsonStr;
                            console.log(`Found rentals array using pattern: ${pattern}`);
                            break;
                        }
                    }
                } catch (e) {
                    // Continue trying other patterns
                }
            }
            if (rentalsData.length > 0) break;
        }
        if (rentalsData.length > 0) break;
    }
    
    // Strategy 2: Try to find the entire data object
    if (rentalsData.length === 0) {
        for (let script of scripts) {
            const content = script.textContent;
            const dataMatch = content.match(/(?:data\s*=\s*|var\s+\w+\s*=\s*)(\{[\s\S]*?\})\s*(?:;|$)/);
            if (dataMatch) {
                try {
                    let jsonStr = dataMatch[1];
                    jsonStr = jsonStr.replace(/,\s*}/g, '}');
                    jsonStr = jsonStr.replace(/,\s*\]/g, ']');
                    jsonStr = jsonStr.replace(/,\s*([\]}])/g, '$1');
                    
                    const parsed = JSON.parse(jsonStr);
                    if (parsed.rentals && Array.isArray(parsed.rentals) && parsed.rentals.length > 0) {
                        rentalsData = parsed.rentals;
                        rawRentalsString = JSON.stringify(parsed.rentals);
                        console.log('Found rentals array from data object');
                        break;
                    }
                } catch (e) {
                    // Continue
                }
            }
        }
    }
    
    // Strategy 3: Try to extract individual rental objects
    if (rentalsData.length === 0) {
        for (let script of scripts) {
            const content = script.textContent;
            const rentalMatches = content.match(/\{"RentalKey":"[^"]+","RentalType":\d+,"ModelKey":"[^"]+","ModelIdentification":\d+,"Beds":\d+[,\s\S]*?\}/g);
            if (rentalMatches && rentalMatches.length > 0) {
                try {
                    const parsedRentals = [];
                    for (let rentalStr of rentalMatches) {
                        try {
                            let cleanStr = rentalStr.replace(/,\s*}/g, '}');
                            cleanStr = cleanStr.replace(/,\s*([\]}])/g, '$1');
                            const parsed = JSON.parse(cleanStr);
                            if (parsed.Rent !== undefined) {
                                parsedRentals.push(parsed);
                            }
                        } catch (e) {
                            // Skip individual parsing errors
                        }
                    }
                    if (parsedRentals.length > 0) {
                        rentalsData = parsedRentals;
                        console.log(`Found ${rentalsData.length} rentals from individual object extraction`);
                        break;
                    }
                } catch (e) {
                    // Continue
                }
            }
        }
    }

    // Get sqft from Schema.org data
    const schemaSqft = extractSchemaSqft();
    console.log(`Found ${Object.keys(schemaSqft).length} sqft entries in Schema.org data`);
    console.log('Schema sqft keys:', Object.keys(schemaSqft));

    if (!rentalsData || rentalsData.length === 0) {
        console.warn('No rentals data found in page scripts.');
        return [];
    }

    console.log(`Successfully extracted ${rentalsData.length} rental entries`);
    console.log('First rental entry sample:', rentalsData[0]);

    // FIRST: Build a map of model names to sqft from schema data
    // This will help us match units even when the names don't exactly match
    const modelToSqft = {};
    const normalizedModelNames = {};
    
    for (const [key, sqft] of Object.entries(schemaSqft)) {
        // Store by exact key
        modelToSqft[key] = sqft;
        
        // Store normalized version (remove punctuation, lowercase)
        const normalized = key.toLowerCase().replace(/[^a-z0-9]/g, '');
        normalizedModelNames[normalized] = sqft;
        
        // If it has a unit number at the end (like "3309"), also store just the unit number
        const unitMatch = key.match(/(\d+)$/);
        if (unitMatch) {
            modelToSqft[unitMatch[1]] = sqft;
        }
        
        // If it has a format like "3 Bed | 2 Bath", store that too
        const bedMatch = key.match(/(\d+)\s*Bed/i);
        const bathMatch = key.match(/(\d+)\s*Bath/i);
        if (bedMatch && bathMatch) {
            const modelKey = `${bedMatch[1]} Bed | ${bathMatch[1]} Bath`;
            modelToSqft[modelKey] = sqft;
        }
    }

    const units = [];
    const seenUnits = new Set(); // For deduplication
    
    for (let rental of rentalsData) {
        // Skip if no price
        if (!rental.Rent) continue;

        // Get beds as a number
        let beds = rental.Beds;
        if (typeof beds !== 'number') {
            const bedMatch = (rental.BedsText || '').match(/(\d+\.?\d*)/);
            beds = bedMatch ? parseFloat(bedMatch[1]) : null;
        }

        // Skip if beds is null or < 3
        if (beds === null || beds < 3) {
            continue;
        }

        // Skip if AvailabilityStatus is 2 (Not Available)
        if (rental.AvailabilityStatus === 2) {
            console.log(`Skipping ${rental.Name || 'unnamed'}: Not available (status ${rental.AvailabilityStatus})`);
            continue;
        }

        // Skip if the unit costs more than $3,500
        if (rental.Rent > 3500) {
            console.log(`Skipping ${rental.Name || 'unnamed'}: Price $${rental.Rent} > $3500`);
            continue;
        }

        // Determine if unit is available
        const availableText = rental.AvailableDateText || '';
        const isAvailable = availableText && 
            !availableText.toLowerCase().includes("not available") && 
            !availableText.toLowerCase().includes("unavailable") &&
            rental.AvailabilityStatus === 1;

        // Try to get sqft from rentals data first
        let sqft = rental.SquareFeet || rental.MaxSquareFeet || null;
        
        // If sqft is missing, try to get it from Schema.org data
        if (!sqft || sqft === 0) {
            const name = rental.Name || '';
            const modelKey = rental.ModelKey || '';
            
            // Try various matching strategies
            let foundSqft = null;
            
            // 1. Try exact name match
            if (modelToSqft[name]) {
                foundSqft = modelToSqft[name];
            }
            // 2. Try matching by ModelKey
            else if (modelKey && modelToSqft[modelKey]) {
                foundSqft = modelToSqft[modelKey];
            }
            // 3. Try by unit number at the end of the name
            else {
                const unitMatch = name.match(/(\d+)$/);
                if (unitMatch && modelToSqft[unitMatch[1]]) {
                    foundSqft = modelToSqft[unitMatch[1]];
                }
                // 4. Try by normalized name
                else {
                    const normalized = name.toLowerCase().replace(/[^a-z0-9]/g, '');
                    if (normalizedModelNames[normalized]) {
                        foundSqft = normalizedModelNames[normalized];
                    }
                    // 5. Try by matching bed/bath pattern
                    else {
                        const bedMatch = name.match(/(\d+)\s*Bed/i);
                        const bathMatch = name.match(/(\d+)\s*Bath/i);
                        if (bedMatch && bathMatch) {
                            const modelKey = `${bedMatch[1]} Bed | ${bathMatch[1]} Bath`;
                            if (modelToSqft[modelKey]) {
                                foundSqft = modelToSqft[modelKey];
                            }
                        }
                    }
                }
            }
            
            if (foundSqft) {
                sqft = foundSqft;
                console.log(`✅ Assigned sqft ${sqft} to ${name}`);
            } else {
                console.log(`⚠️ No sqft found for ${name} (ModelKey: ${modelKey})`);
            }
        }

        // Create a unique key for this unit to avoid duplicates
        // Use ModelKey + Rent as the unique identifier (since different units can have same name)
        const uniqueKey = `${rental.ModelKey || rental.Name}-${rental.Rent}`;
        
        // Also check if we've seen this unit by name and price (within tolerance)
        let isDuplicate = false;
        for (const existingUnit of units) {
            // If same name/price and same beds, it's a duplicate
            if (existingUnit.unit === rental.Name && 
                Math.abs(existingUnit.price - rental.Rent) < 10 &&
                existingUnit.beds === beds) {
                isDuplicate = true;
                // If this one has sqft and the existing doesn't, merge the sqft
                if (sqft && !existingUnit.hasSqft) {
                    existingUnit.sqft = sqft;
                    existingUnit.hasSqft = true;
                    existingUnit.sqftRange = `${sqft.toLocaleString()}`;
                }
                break;
            }
        }
        
        if (isDuplicate) {
            console.log(`Skipping duplicate: ${rental.Name} - $${rental.Rent}`);
            continue;
        }

        console.log(`✅ Found 3+ bedroom unit: ${rental.Name} - ${rental.Beds} beds, $${rental.Rent}, ${sqft || 'unknown'} sqft`);

        const unit = {
            unit: rental.Name || rental.ModelKey || '',
            beds: beds,
            baths: rental.Baths || null,
            price: rental.Rent,
            sqft: sqft,
            available: availableText,
            isAvailable: isAvailable,
            isRange: rental.Rent !== rental.MaxRent,
            priceRange: rental.Rent === rental.MaxRent ? 
                `$${rental.Rent.toLocaleString()}` : 
                `$${rental.Rent.toLocaleString()}–$${rental.MaxRent.toLocaleString()}`,
            sqftRange: sqft ? `${sqft.toLocaleString()}` : "N/A",
            hasSqft: sqft !== null && sqft > 0,
            modelKey: rental.ModelKey || '',
            // Store the rental key for debugging
            rentalKey: rental.RentalKey || ''
        };

        units.push(unit);
        seenUnits.add(uniqueKey);
    }

    console.log(`Found ${units.length} 3+ bed listings from rentals data (filtered to under $3,500).`);
    console.log(`${units.filter(u => u.hasSqft).length} have sqft data.`);
    
    // Log all found units
    if (units.length > 0) {
        console.log('All found units:');
        units.forEach(u => {
            console.log(`  - ${u.unit}: ${u.beds} beds, $${u.price}, ${u.hasSqft ? u.sqft + ' sqft' : 'NO SQFT'}, ${u.isAvailable ? 'Available' : 'Unavailable'}`);
        });
    }
    
    return units;
}

////////////////////////////////////////////////////////////
// FIND BEST VALUE UNIT - FINDS ABSOLUTE BEST AND BEST AVAILABLE
// Handles units without sqft by using lowest price instead
////////////////////////////////////////////////////////////

function findBestUnits(units) {
    if (!units.length) return { bestOverall: null, bestAvailable: null, cheapestOverall: null, cheapestAvailable: null };

    // Function to find the best value within a set (by price/sqft if available, otherwise by lowest price)
    function findBestInSet(unitSet) {
        if (!unitSet.length) return null;
        
        // Split into units with sqft and without
        const withSqft = unitSet.filter(u => u.hasSqft === true);
        const withoutSqft = unitSet.filter(u => u.hasSqft !== true);
        
        let best = null;
        
        // Find best by price/sqft among units with sqft
        if (withSqft.length) {
            best = withSqft.reduce((best, u) => {
                const ratio = u.price / u.sqft;
                return (!best || ratio < best.ratio) ? { ...u, ratio } : best;
            }, null);
        }
        
        // If no units with sqft, find cheapest by price
        if (!best && withoutSqft.length) {
            best = withoutSqft.reduce((best, u) => {
                return (!best || u.price < best.price) ? { ...u, ratio: null } : best;
            }, null);
            if (best) {
                best.note = "No sqft available - using lowest price";
            }
        }
        
        return best;
    }

    // Find the absolute best value (regardless of availability)
    const bestOverall = findBestInSet(units);
    
    // Find the best among available units
    const availableUnits = units.filter(u => u.isAvailable === true);
    const bestAvailable = findBestInSet(availableUnits);

    // Find cheapest overall (for when sqft is missing)
    const cheapestOverall = units.reduce((best, u) => {
        return (!best || u.price < best.price) ? u : best;
    }, null);
    
    const cheapestAvailable = availableUnits.length ? availableUnits.reduce((best, u) => {
        return (!best || u.price < best.price) ? u : best;
    }, null) : null;

    console.log(`Absolute best value: ${bestOverall ? bestOverall.unit : 'None'} at ${bestOverall ? (bestOverall.ratio ? '$' + bestOverall.ratio.toFixed(2) + '/sqft' : 'lowest price: $' + bestOverall.price) : 'N/A'}`);
    console.log(`Best available: ${bestAvailable ? bestAvailable.unit : 'None'} at ${bestAvailable ? (bestAvailable.ratio ? '$' + bestAvailable.ratio.toFixed(2) + '/sqft' : 'lowest price: $' + bestAvailable.price) : 'N/A'}`);

    return { bestOverall, bestAvailable, cheapestOverall, cheapestAvailable };
}

////////////////////////////////////////////////////////////
// DESCRIPTION
////////////////////////////////////////////////////////////

function getDescription() {
    const el =
        $("#descriptionSection") ||
        $(".descriptionSection") ||
        $(".description");

    if (!el) return "";

    let t = text(el);
    if (t.length > 2000) {
        console.warn("getDescription(): matched element looks too big, truncating — check your selector", el);
        t = t.slice(0, 2000) + "…";
    }
    return t;
}

////////////////////////////////////////////////////////////
// BODY TEXT
////////////////////////////////////////////////////////////

const body = clean(document.body.innerText);

////////////////////////////////////////////////////////////
// PROPERTY OBJECT
////////////////////////////////////////////////////////////

const property = {};

property.Name = text($("#propertyName")) || text($("h1"));
property.Address = text($(".propertyAddressContainer")) || text($("address"));
property.Phone = text($(".phoneNumber"));
property.URL = location.href;

property.PriceRange = findLabel("Monthly Rent");
property.Bedrooms = findLabel("Bedrooms");
property.Bathrooms = findLabel("Bathrooms");
property.SquareFeet = findLabel("Square Feet");

property.YearBuilt = (body.match(/Built(?: in)?\s+(\d{4})/i) || [])[1] || "";

function score(type) {
    return text($(`#vendor-score-cards .score-card.${type} .score-number`));
}
property.WalkScore = score("walk");
property.TransitScore = score("transit");
property.DrivabilityScore = score("carfriendly");
property.BikeScore = score("bike");

property.SoundScore = text($("#sound-score-section .sound-score-number"));
property.SoundStatus = text($("#sound-score-section .sound-score-status"));
property.SoundTraffic = text($("#sound-score-section .ss-traffic-data"));
property.SoundAirport = text($("#sound-score-section .ss-airports-data"));
property.SoundBusinesses = text($("#sound-score-section .ss-business-data"));

property.Amenities = findSection("Amenities");
property.PetPolicy = extractFeesPanel("#fees-policies-pet-fees-tab") || findSection("Pet");
property.Parking = extractFeesPanel("#fees-policies-parking-tab") || findSection("Parking");
property.Utilities = extractUtilities() || findSection("Utilities");
property.LeaseTerms = extractLeaseOptions() || findSection("Lease");
property.Fees = findSection("Fees");
property.Description = getDescription();

////////////////////////////////////////////////////////////
// BEST VALUE UNITS
////////////////////////////////////////////////////////////

// PRIMARY: Try to extract from rentals data
let units = extractUnitsFromData();

// FALLBACK: If no units found from data, use DOM parsers
if (units.length === 0) {
    console.warn('No units found from rentals data, falling back to DOM parsing...');

    // FIX: backfill sqft for individual unit rows from the JSON-LD schema
    // data (this was previously only done on the primary rentals-data path,
    // leaving DOM-parsed units with sqft: null even when the schema had it).
    const schemaSqft = extractSchemaSqft();
    const unitRows = extractUnits(schemaSqft);
    const floorplanRows = extractFloorplanModels();

    // FIX: floorplanRows are aggregate "model" cards (e.g. "3 Bed | 2 Bath"),
    // not real listings — they duplicate whatever specific units already
    // appear in unitRows, but with a less reliable, floorplan-wide
    // availability flag. Previously both were concatenated and ranked as if
    // they were independent units, which let a stale "unavailable" aggregate
    // card outrank the real, available unit it was describing. Only keep a
    // floorplan row when no specific unit row exists yet for that bed/bath
    // combo, so it's used purely as a last resort, not a competing duplicate.
    const coveredBedBath = new Set(unitRows.map(u => `${u.beds}-${u.baths}`));
    const supplementalFloorplanRows = floorplanRows.filter(
        u => !coveredBedBath.has(`${u.beds}-${u.baths}`)
    );

    units = [...unitRows, ...supplementalFloorplanRows];
    // Additional filter for the DOM-based units (though the functions already filter)
    units = units.filter(u => u.price <= 3500);
    console.log(`Found ${units.length} units from DOM parsing (filtered to under $3,500).`);
}

const { bestOverall, bestAvailable, cheapestOverall, cheapestAvailable } = findBestUnits(units);

property.UnitsFound = units.length;
property.UnitsAvailable = units.filter(u => u.isAvailable).length;
property.UnitsUnavailable = units.filter(u => !u.isAvailable).length;

// Helper to format unit info consistently
function formatUnit(u) {
    if (!u) return "";
    if (u.ratio !== undefined && u.ratio !== null) {
        return u.unit;
    }
    return u.unit;
}

function formatPrice(u) {
    if (!u) return "";
    if (u.isRange) {
        return `$${u.price.toLocaleString()} (low of ${u.priceRange})`;
    }
    return `$${u.price.toLocaleString()}`;
}

function formatSqft(u) {
    if (!u) return "";
    if (u.hasSqft) {
        return u.sqft.toLocaleString();
    }
    return "N/A";
}

function formatPricePerSqft(u) {
    if (!u) return "";
    if (u.ratio !== undefined && u.ratio !== null) {
        return `$${u.ratio.toFixed(2)}/sqft`;
    }
    if (u.hasSqft === false || u.sqft === null) {
        return "N/A (no sqft)";
    }
    return "";
}

// Overall Best Value (regardless of availability) - prioritizes units with sqft
property.BestValueUnit = bestOverall ? bestOverall.unit : "";
property.BestValueBeds = bestOverall ? bestOverall.beds : "";
property.BestValueBaths = bestOverall ? bestOverall.baths : "";
property.BestValuePrice = bestOverall ? formatPrice(bestOverall) : "";
property.BestValueSqFt = bestOverall ? formatSqft(bestOverall) : "";
property.BestValuePricePerSqFt = bestOverall ? formatPricePerSqft(bestOverall) : "";
property.BestValueAvailable = bestOverall ? bestOverall.available : "";
property.BestValueIsAvailable = bestOverall ? (bestOverall.isAvailable ? "Yes" : "No") : "";

// Best Available Unit (for when the overall best is unavailable)
property.BestAvailableUnit = bestAvailable ? bestAvailable.unit : "";
property.BestAvailableBeds = bestAvailable ? bestAvailable.beds : "";
property.BestAvailableBaths = bestAvailable ? bestAvailable.baths : "";
property.BestAvailablePrice = bestAvailable ? formatPrice(bestAvailable) : "";
property.BestAvailableSqFt = bestAvailable ? formatSqft(bestAvailable) : "";
property.BestAvailablePricePerSqFt = bestAvailable ? formatPricePerSqft(bestAvailable) : "";
property.BestAvailableAvailability = bestAvailable ? bestAvailable.available : "";

// If the overall best is available, the best available is the same
if (bestOverall && bestAvailable && bestOverall.unit === bestAvailable.unit) {
    property.Note = "Best available is the same as overall best";
} else if (bestOverall && !bestOverall.isAvailable && bestAvailable) {
    property.Note = `Overall best (${bestOverall.unit}) is unavailable. Best available is ${bestAvailable.unit}`;
} else if (bestOverall && !bestOverall.hasSqft) {
    property.Note = "No sqft available for best unit - using lowest price";
} else {
    property.Note = "";
}

////////////////////////////////////////////////////////////
// DEBUG: log every unit found, and each field's length
////////////////////////////////////////////////////////////

if (units.length) {
    const withSqft = units.filter(u => u.hasSqft);
    const withoutSqft = units.filter(u => !u.hasSqft);
    console.log(`Found ${units.length} 3+ bed listing(s) under $3,500:`);
    console.log(`  - ${units.filter(u => u.isAvailable).length} available`);
    console.log(`  - ${units.filter(u => !u.isAvailable).length} unavailable`);
    console.log(`  - ${withSqft.length} with sqft`);
    console.log(`  - ${withoutSqft.length} without sqft (using lowest price)`);
    console.table(units);
} else {
    console.warn("No 3+ bed listings found under $3,500.");
}

console.table(
    Object.entries(property).map(([field, value]) => ({
        field,
        length: String(value).length,
        preview: String(value).slice(0, 80)
    }))
);

////////////////////////////////////////////////////////////
// COPY VALUES WITH BETTER UI
////////////////////////////////////////////////////////////

// Create the TSV string (tab-separated values for Excel/Google Sheets)
const tsvData = Object.values(property).map(v => String(v ?? "")).join("\t");
// Also keep the vertical version for readability
const verticalData = Object.values(property).map(v => String(v ?? "")).join("\n");

// Function to show a copy button with preview
function showCopyUI(tsv, verticalData) {
    // Create overlay container
    const overlay = document.createElement("div");
    overlay.style.cssText = `
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.7);
        z-index: 999999;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    `;

    // Create modal
    const modal = document.createElement("div");
    modal.style.cssText = `
        background: white;
        border-radius: 12px;
        padding: 30px;
        max-width: 700px;
        width: 90%;
        max-height: 80vh;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        overflow-y: auto;
    `;

    // Title
    const title = document.createElement("h2");
    const availabilityStatus = units.filter(u => u.isAvailable).length > 0 
        ? "✅ Available units found!" 
        : "⚠️ No available units found";
    title.textContent = `📋 Apartment Data Copied! ${availabilityStatus}`;
    title.style.cssText = `
        margin: 0 0 10px 0;
        font-size: 24px;
        font-weight: 600;
        color: #1a1a1a;
    `;
    modal.appendChild(title);

    // Subtitle
    const subtitle = document.createElement("p");
    const availableCount = units.filter(u => u.isAvailable).length;
    const totalCount = units.length;
    const withSqftCount = units.filter(u => u.hasSqft).length;
    subtitle.textContent = `Found ${totalCount} 3+ bedroom units under $3,500 (${availableCount} available, ${totalCount - availableCount} unavailable). ${withSqftCount} have sqft data, ${totalCount - withSqftCount} use lowest price.`;
    subtitle.style.cssText = `
        margin: 0 0 20px 0;
        color: #666;
        font-size: 14px;
        line-height: 1.5;
    `;
    modal.appendChild(subtitle);

    // Preview section
    const previewLabel = document.createElement("div");
    previewLabel.textContent = "Preview (first few values):";
    previewLabel.style.cssText = `
        font-size: 13px;
        font-weight: 600;
        color: #555;
        margin-bottom: 8px;
    `;
    modal.appendChild(previewLabel);

    const previewBox = document.createElement("div");
    const previewValues = Object.values(property).slice(0, 10).map(v => String(v ?? "").slice(0, 50));
    previewBox.textContent = previewValues.join(" | ");
    previewBox.style.cssText = `
        background: #f5f5f5;
        padding: 12px;
        border-radius: 6px;
        font-family: 'Courier New', monospace;
        font-size: 12px;
        color: #333;
        margin-bottom: 20px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        border: 1px solid #e0e0e0;
    `;
    modal.appendChild(previewBox);

    // Show best value info
    if (bestOverall) {
        const isAvailable = bestOverall.isAvailable;
        const hasSqft = bestOverall.hasSqft;
        const bestInfo = document.createElement("div");
        bestInfo.style.cssText = `
            background: ${isAvailable ? '#ecfdf5' : '#fef3c7'};
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 12px;
            border-left: 4px solid ${isAvailable ? '#10b981' : '#f59e0b'};
            font-size: 13px;
            color: #1f2937;
        `;
        const pricePerSqftDisplay = bestOverall.ratio !== undefined && bestOverall.ratio !== null 
            ? `$${bestOverall.ratio.toFixed(2)}/sqft` 
            : 'N/A (no sqft)';
        bestInfo.innerHTML = `
            <strong>🏆 Best Value (Overall): ${bestOverall.unit}</strong><br>
            ${bestOverall.beds} beds, ${bestOverall.baths} baths • ${bestOverall.hasSqft ? bestOverall.sqft + ' sq ft' : 'No sqft available'} • ${bestOverall.hasSqft ? '$' + (bestOverall.price/bestOverall.sqft).toFixed(2) + '/sqft' : 'Using lowest price: $' + bestOverall.price}<br>
            Price: ${bestOverall.isRange ? bestOverall.priceRange : '$' + bestOverall.price.toLocaleString()}<br>
            Availability: <strong>${isAvailable ? '✅ Available' : '❌ Not Available'}</strong>
        `;
        modal.appendChild(bestInfo);

        // If the best overall is unavailable, show the best available alternative
        if (!isAvailable && bestAvailable) {
            const altInfo = document.createElement("div");
            altInfo.style.cssText = `
                background: #ecfdf5;
                padding: 12px 16px;
                border-radius: 6px;
                margin-bottom: 12px;
                border-left: 4px solid #10b981;
                font-size: 13px;
                color: #1f2937;
            `;
            const altPricePerSqft = bestAvailable.ratio !== undefined && bestAvailable.ratio !== null 
                ? `$${bestAvailable.ratio.toFixed(2)}/sqft` 
                : 'N/A (no sqft)';
            altInfo.innerHTML = `
                <strong>🔄 Best Available Alternative: ${bestAvailable.unit}</strong><br>
                ${bestAvailable.beds} beds, ${bestAvailable.baths} baths • ${bestAvailable.hasSqft ? bestAvailable.sqft + ' sq ft' : 'No sqft available'} • ${bestAvailable.hasSqft ? '$' + (bestAvailable.price/bestAvailable.sqft).toFixed(2) + '/sqft' : 'Lowest price: $' + bestAvailable.price}<br>
                Price: ${bestAvailable.isRange ? bestAvailable.priceRange : '$' + bestAvailable.price.toLocaleString()}<br>
                Availability: ✅ Available
            `;
            modal.appendChild(altInfo);
            
            // Show comparison if both have sqft
            if (bestOverall.hasSqft && bestAvailable.hasSqft) {
                const diff = ((bestOverall.price/bestOverall.sqft) - (bestAvailable.price/bestAvailable.sqft)).toFixed(2);
                const diffPercent = ((diff / (bestOverall.price/bestOverall.sqft)) * 100).toFixed(1);
                const comparison = document.createElement("div");
                comparison.style.cssText = `
                    background: #f3f4f6;
                    padding: 10px 16px;
                    border-radius: 6px;
                    margin-bottom: 16px;
                    font-size: 12px;
                    color: #4b5563;
                    text-align: center;
                `;
                comparison.innerHTML = `
                    <span style="color: #ef4444;">Best overall is $${diff}/sqft cheaper (${diffPercent}% better)</span>
                `;
                modal.appendChild(comparison);
            }
        }
    }

    // Button container
    const buttonContainer = document.createElement("div");
    buttonContainer.style.cssText = `
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
    `;

    // Copy button (TSV format - best for Excel)
    const copyTsvBtn = document.createElement("button");
    copyTsvBtn.textContent = "📊 Copy for Excel (Tab-separated)";
    copyTsvBtn.style.cssText = `
        flex: 1;
        min-width: 200px;
        padding: 12px 20px;
        background: #0a7c3e;
        color: white;
        border: none;
        border-radius: 6px;
        font-size: 15px;
        font-weight: 500;
        cursor: pointer;
        transition: background 0.2s;
    `;
    copyTsvBtn.onmouseover = () => copyTsvBtn.style.background = "#0b8f48";
    copyTsvBtn.onmouseout = () => copyTsvBtn.style.background = "#0a7c3e";
    
    copyTsvBtn.onclick = async () => {
        try {
            await navigator.clipboard.writeText(tsv);
            copyTsvBtn.textContent = "✅ Copied!";
            copyTsvBtn.style.background = "#0b8f48";
            setTimeout(() => {
                copyTsvBtn.textContent = "📊 Copy for Excel (Tab-separated)";
                copyTsvBtn.style.background = "#0a7c3e";
            }, 2000);
        } catch (err) {
            // Fallback: select the text
            copyTsvBtn.textContent = "❌ Failed, selecting text...";
            const tempArea = document.createElement("textarea");
            tempArea.value = tsv;
            document.body.appendChild(tempArea);
            tempArea.select();
            document.execCommand("copy");
            document.body.removeChild(tempArea);
            setTimeout(() => {
                copyTsvBtn.textContent = "📊 Copy for Excel (Tab-separated)";
                copyTsvBtn.style.background = "#0a7c3e";
            }, 2000);
        }
    };
    buttonContainer.appendChild(copyTsvBtn);

    // Copy button (Vertical format - easier to read)
    const copyVerticalBtn = document.createElement("button");
    copyVerticalBtn.textContent = "📝 Copy Vertical (Readable)";
    copyVerticalBtn.style.cssText = `
        flex: 1;
        min-width: 200px;
        padding: 12px 20px;
        background: #2563eb;
        color: white;
        border: none;
        border-radius: 6px;
        font-size: 15px;
        font-weight: 500;
        cursor: pointer;
        transition: background 0.2s;
    `;
    copyVerticalBtn.onmouseover = () => copyVerticalBtn.style.background = "#1d4ed8";
    copyVerticalBtn.onmouseout = () => copyVerticalBtn.style.background = "#2563eb";
    
    copyVerticalBtn.onclick = async () => {
        try {
            await navigator.clipboard.writeText(verticalData);
            copyVerticalBtn.textContent = "✅ Copied!";
            copyVerticalBtn.style.background = "#1d4ed8";
            setTimeout(() => {
                copyVerticalBtn.textContent = "📝 Copy Vertical (Readable)";
                copyVerticalBtn.style.background = "#2563eb";
            }, 2000);
        } catch (err) {
            // Fallback: select the text
            copyVerticalBtn.textContent = "❌ Failed, selecting text...";
            const tempArea = document.createElement("textarea");
            tempArea.value = verticalData;
            document.body.appendChild(tempArea);
            tempArea.select();
            document.execCommand("copy");
            document.body.removeChild(tempArea);
            setTimeout(() => {
                copyVerticalBtn.textContent = "📝 Copy Vertical (Readable)";
                copyVerticalBtn.style.background = "#2563eb";
            }, 2000);
        }
    };
    buttonContainer.appendChild(copyVerticalBtn);

    // Close button
    const closeBtn = document.createElement("button");
    closeBtn.textContent = "✕ Close";
    closeBtn.style.cssText = `
        padding: 12px 24px;
        background: #e5e7eb;
        color: #374151;
        border: none;
        border-radius: 6px;
        font-size: 15px;
        font-weight: 500;
        cursor: pointer;
        transition: background 0.2s;
    `;
    closeBtn.onmouseover = () => closeBtn.style.background = "#d1d5db";
    closeBtn.onmouseout = () => closeBtn.style.background = "#e5e7eb";
    closeBtn.onclick = () => document.body.removeChild(overlay);
    buttonContainer.appendChild(closeBtn);

    modal.appendChild(buttonContainer);

    // Add keyboard shortcut: press ESC to close
    document.addEventListener('keydown', function escHandler(e) {
        if (e.key === 'Escape') {
            if (document.body.contains(overlay)) {
                document.body.removeChild(overlay);
                document.removeEventListener('keydown', escHandler);
            }
        }
    });

    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}

// Try to auto-copy, but always show the UI for manual copying too
try {
    if (navigator.clipboard && document.hasFocus()) {
        await navigator.clipboard.writeText(tsvData);
        console.log("Clipboard auto-copy succeeded (TSV format).");
    }
} catch (err) {
    console.log("Auto-copy failed, but UI will provide copy buttons.");
}

// Always show the copy UI for manual copying
showCopyUI(tsvData, verticalData);

})();