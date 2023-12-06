function imageZoom(imgID, resultIDs, n_images) {
    var img, lens, result, cx, cy, x, y;
    var img_ind = 0

    img = document.getElementById(imgID);

    /* Create lens: */
    lens = document.createElement("DIV");

    lens.setAttribute("class", "img-zoom-lens");
    // lens.setAttribute("color", "red");
    lens.style.border = "3px solid yellow";

    /* Insert lens: */
    img.parentElement.insertBefore(lens, img);
    
    /* Get zoom in image id*/
    var res = []
    for (var i = 0; i < resultIDs.length; i++) {
        res.push(document.getElementById(resultIDs[i]));
        
        /* Calculate the ratio between result DIV and lens: */
        cx = res.at(-1).offsetWidth / lens.offsetWidth;
        cy = res.at(-1).offsetHeight / lens.offsetHeight;

        /* Set background properties for the result DIV */
        res.at(-1).style.backgroundImage = "url('" + res.at(-1).dataset.image + ("000" + img_ind).slice(-3) + ".png')";
        res.at(-1).style.backgroundSize = img.width * cx  + "px " + img.height * cy + "px";
    }
    
    cx = res[0].offsetWidth / lens.offsetWidth;
    cy = res[0].offsetHeight / lens.offsetHeight;
    
    /* Execute a function when someone moves the cursor over the image, or the lens: */
    lens.addEventListener("mousemove", moveLens);
    img.addEventListener("mousemove", moveLens);

    /* Change images when click: */
    lens.addEventListener("click", nextImage);
    img.addEventListener("click", nextImage);

    var scenes = ["Chair", "Drums", "Ficus", "Hotdog", "Lego", "Materials", "Mic", "Ship"]
    var archVariants = ["NeRF", "NAS-NeRF-S", "NAS-NeRF-XS", "NAS-NeRF-XXS"]
    var archDetails = 
    {
        "Chair": {
            "NAS-NeRF-S": {
                "Params": "0.32 M <b>(3.46x)</b>",
                "FLOPs": "237.57 G <b>(2.42x)</b>"
            },
            "NAS-NeRF-XS": {
                "Params": "0.08 M <b>(14.33x)</b>",
                "FLOPs": "48.56 G <b>(11.82x)</b>"
            },
            "NAS-NeRF-XXS": {
                "Params": "0.05 M <b>(21.92x)</b>",
                "FLOPs": "28.01 G <b>(20.49x)</b>"
            }
        },
        "Drums": {
            "NAS-NeRF-S": {
                "Params": "0.32 M <b>(3.46x)</b>",
                "FLOPs": "237.57 G <b>(2.42x)</b>"
            },
            "NAS-NeRF-XS": {
                "Params": "0.08 M <b>(13.81x)</b>",
                "FLOPs": "49.29 G <b>(11.65x)</b>"
            },
            "NAS-NeRF-XXS": {
                "Params": "0.05 M <b>(21.82x)</b>",
                "FLOPs": "28.08 G <b>(20.45x)</b>"
            }
        },
        "Ficus": {
            "NAS-NeRF-S": {
                "Params": "0.33 M <b>(3.32x)</b>",
                "FLOPs": "247.57 G <b>(2.32x)</b>"
            },
            "NAS-NeRF-XS": {
                "Params": "0.18 M <b>(5.99x)</b>",
                "FLOPs": "132.33 G <b>(4.34x)</b>"
            },
            "NAS-NeRF-XXS": {
                "Params": "0.06 M <b>(18.94x)</b>",
                "FLOPs": "34.17 G <b>(16.80x)</b>"
            }
        },
        "Hotdog": {
            "NAS-NeRF-S": {
                "Params": "0.32 M <b>(3.46x)</b>",
                "FLOPs": "237.57 G <b>(2.42x)</b>"
            },
            "NAS-NeRF-XS": {
                "Params": "0.07 M <b>(15.51x)</b>",
                "FLOPs": "43.98 G <b>(13.05x)</b>"
            },
            "NAS-NeRF-XXS": {
                "Params": "0.05 M <b>(23.05x)</b>",
                "FLOPs": "25.98 G <b>(22.10x)</b>"
            }
        },
        "Lego": {
            "NAS-NeRF-S": {
                "Params": "0.39 M <b>(2.83x)</b>",
                "FLOPs": "262.61 G <b>(2.19x)</b>"
            },
            "NAS-NeRF-XS": {
                "Params": "0.09 M <b>(12.19x)</b>",
                "FLOPs": "58.98 G <b>(9.73x)</b>"
            },
            "NAS-NeRF-XXS": {
                "Params": "0.05 M <b>(20.64x)</b>",
                "FLOPs": "29.03 G <b>(19.78x)</b>"
            }
        },
        "Materials": {
            "NAS-NeRF-S": {
                "Params": "0.19 M <b>(5.74x)</b>",
                "FLOPs": "137.17 G <b>(4.19x)</b>"
            },
            "NAS-NeRF-XS": {
                "Params": "0.07 M <b>(15.51x)</b>",
                "FLOPs": "43.98 G <b>(13.05x)</b>"
            },
            "NAS-NeRF-XXS": {
                "Params": "0.05 M <b>(21.92x)</b>",
                "FLOPs": "28.01 G <b>(20.49x)</b>"
            }
        },
        "Mic": {
            "NAS-NeRF-S": {
                "Params": "0.23 M <b>(4.83x)</b>",
                "FLOPs": "146.53 G <b>(3.92x)</b>"
            },
            "NAS-NeRF-XS": {
                "Params": "0.06 M <b>(18.94x)</b>",
                "FLOPs": "34.17 G <b>(16.80x)</b>"
            },
            "NAS-NeRF-XXS": {
                "Params": "0.05 M <b>(21.82x)</b>",
                "FLOPs": "28.08 G <b>(20.45x)</b>"
            }
        },
        "Ship": {
            "NAS-NeRF-S": {
                "Params": "0.32 M <b>(3.46x)</b>",
                "FLOPs": "237.57 G <b>(2.42x)</b>"
            },
            "NAS-NeRF-XS": {
                "Params": "0.06 M <b>(18.86x)</b>",
                "FLOPs": "34.23 G <b>(16.77x)</b>"
            },
            "NAS-NeRF-XXS": {
                "Params": "0.05 M <b>(23.05x)</b>",
                "FLOPs": "26.11 G <b>(21.99x)</b>"
            }
        }
    }


    function moveLens(e) {
        /* Prevent any other actions that may occur when moving over the image */
        e.preventDefault();
        
        // Resize zoomed patches to cope with various resolutions
        for (var i = 0; i < res.length; i++) {
            res[i].style.backgroundSize = img.width * cx  + "px " + img.height * cy + "px";
        }
        
        /* Get the cursor's x and y positions: */
        var pos = getCursorPos(e);
        /* Calculate the position of the lens: */
        x = pos.x - (lens.offsetWidth / 2);
        y = pos.y - (lens.offsetHeight / 2);
        /* Prevent the lens from being positioned outside the image: */
        if (x > (img.width - lens.offsetWidth)) {x = img.width - lens.offsetWidth;}
        if (x < 0) {x = 0;}
        if (y > (img.height - lens.offsetHeight)) {y = img.height - lens.offsetHeight;}
        if (y < 0) {y = 0;}
        /* Set the position of the lens: */
        lens.style.left = img.offsetLeft + x + "px";
        lens.style.top = img.offsetTop + y + "px";
        
        /* Display what the lens "sees": */
        for (var i = 0; i < res.length; i++) {
            res[i].style.backgroundPosition = "-" + (x * cx) + "px -" + (y * cy) + "px"; 
        }
        
    }
    
    function nextImage(e) {
        e.preventDefault();
        
        img_ind = (((img_ind + 1) < n_images) ? img_ind + 1 : 0)
        
        /* Change reference image */
        img.src = img.dataset.image + ("000" + img_ind).slice(-3) + ".png"

        /* Change zoomed in patches*/
        currentScene = scenes[img_ind]
        for (var i = 0; i < res.length; i++) {
            res[i].style.backgroundImage = "url('" + res[i].dataset.image + ("000" + img_ind).slice(-3) + ".png')";

            // Update the model details based on the current scene and model variant
            currentarchVariant = archVariants[i]
            console.log(currentarchVariant, currentScene)
            updateArchDetails(currentScene, currentarchVariant);
        }
    }

    function updateArchDetails(scene, archVariant) {
        if (archVariant == "NeRF") {
            var details = {
                "Params": "1.09 M <b>(1x)</b>",
                "FLOPs": "574.14 G <b>(1x)</b>"
            }
        } else {
            var details = archDetails[scene][archVariant];
        }
        console.log("archDetails", archDetails)
        console.log(scene)
        console.log("details", details)
        document.querySelector('.arch-details[data-arch="' + archVariant + '"]').innerHTML = `
            Params: ${details.Params}<br>
            FLOPs: ${details.FLOPs}
        `;
    }

    // Initialize with  the first scene.
    var initialScene = scenes[0];
    for (var i = 0; i < archVariants.length; i++) {
        updateArchDetails(initialScene, archVariants[i]);
    }

    function getCursorPos(e) {
        var a, x = 0, y = 0;
        e = e || window.event;
        /* Get the x and y positions of the image: */
        a = img.getBoundingClientRect();
        /* Calculate the cursor's x and y coordinates, relative to the image: */
        x = e.pageX - a.left;
        y = e.pageY - a.top;
        /* Consider any page scrolling: */
        x = x - window.pageXOffset;
        y = y - window.pageYOffset;
        return {x : x, y : y};
    }
} 
