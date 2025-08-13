package com.uml2papyrus;

import org.eclipse.emf.common.util.Diagnostic;
import org.eclipse.emf.common.util.URI;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.emf.ecore.resource.Resource;
import org.eclipse.emf.ecore.resource.ResourceSet;
import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;
import org.eclipse.emf.ecore.util.Diagnostician;
import org.eclipse.emf.ecore.util.EcoreUtil;
import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;
import org.eclipse.uml2.uml.UMLPackage;
import org.eclipse.uml2.uml.resource.UMLResource;

import java.util.Map;

public class EmfXmiValidator {
    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("Usage: EmfXmiValidator <path-to-model.uml>");
            System.exit(2);
        }
        String path = args[0];
        try {
            // Init EMF/UML resource set
            ResourceSet resourceSet = new ResourceSetImpl();

            // Register default XMI factory and UML factory
            Map<String, Object> extMap = resourceSet.getResourceFactoryRegistry().getExtensionToFactoryMap();
            extMap.put(Resource.Factory.Registry.DEFAULT_EXTENSION, new XMIResourceFactoryImpl());
            extMap.put("uml", UMLResource.Factory.INSTANCE);

            // Initialize UML pathmaps when utility class is available (newer UML2)
            try {
                Class<?> util = Class.forName("org.eclipse.uml2.uml.resources.util.UMLResourcesUtil");
                util.getMethod("init", ResourceSet.class).invoke(null, resourceSet);
            } catch (ClassNotFoundException cnfe) {
                // Older UML2: no UMLResourcesUtil. Proceed without pathmap init.
            } catch (Throwable t) {
                // Any other reflection error: continue; validation may still work without pathmaps
            }
            resourceSet.getPackageRegistry().put(UMLPackage.eNS_URI, UMLPackage.eINSTANCE);

            // Optionally initialize UML2 Types package when available
            try {
                Class<?> typesPkg = Class.forName("org.eclipse.uml2.types.TypesPackage");
                Object eINSTANCE = typesPkg.getField("eINSTANCE").get(null);
                if (eINSTANCE != null) {
                    // Touch to ensure class is initialized
                    eINSTANCE.toString();
                }
            } catch (ClassNotFoundException ignored) {
                // Types package not present in older stacks
            } catch (Throwable t) {
                // ignore
            }

            // Load the model
            URI uri = URI.createFileURI(path);
            Resource resource = resourceSet.getResource(uri, true);
            // Resolve cross references
            EcoreUtil.resolveAll(resource);

            if (resource.getContents().isEmpty()) {
                System.err.println("Loaded resource is empty: " + path);
                System.exit(3);
            }

            EObject root = resource.getContents().get(0);
            Diagnostic diagnostic = Diagnostician.INSTANCE.validate(root);

            if (diagnostic.getSeverity() == Diagnostic.OK) {
                System.out.println("OK: EMF validation passed");
                System.exit(0);
            } else {
                System.err.println("EMF validation reported issues (severity=" + diagnostic.getSeverity() + ")");
                printDiagnostic(diagnostic, "");
                System.exit(1);
            }
        } catch (Exception e) {
            System.err.println("Validator error: " + e.getMessage());
            e.printStackTrace(System.err);
            System.exit(4);
        }
    }

    private static void printDiagnostic(Diagnostic diagnostic, String indent) {
        System.err.println(indent + diagnostic.getMessage());
        for (Diagnostic child : diagnostic.getChildren()) {
            printDiagnostic(child, indent + "  ");
        }
    }
}


